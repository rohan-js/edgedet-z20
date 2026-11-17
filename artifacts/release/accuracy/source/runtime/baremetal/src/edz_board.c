#if !defined(EDZ_XILINX_BAREMETAL)
#error "Build this adapter only in the Vitis standalone BSP with EDZ_XILINX_BAREMETAL defined"
#endif

#include "edz_board.h"
#include "edz_accel_io.h"
#include "edz_protocol.h"

#include "sleep.h"
#include "xaxidma.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "xparameters.h"
#include "xscugic.h"
#include "xtime_l.h"

#include <string.h>

/* HLS ap_ctrl_hs registers. The accelerator has no pointer arguments. */
#define EDZ_CTRL_AP_CTRL 0x00u
#define EDZ_CTRL_GIE 0x04u
#define EDZ_CTRL_IER 0x08u
#define EDZ_CTRL_ISR 0x0cu

#ifndef XPAR_AXIDMA_0_DEVICE_ID
#error "Map the final BSP's AXI DMA device ID to XPAR_AXIDMA_0_DEVICE_ID"
#endif
#if defined(XPAR_FABRIC_AXI_DMA_0_MM2S_INTROUT_INTR)
#define EDZ_MM2S_IRQ XPAR_FABRIC_AXI_DMA_0_MM2S_INTROUT_INTR
#elif defined(XPAR_FABRIC_AXI_DMA_0_MM2S_INTROUT_VEC_ID)
#define EDZ_MM2S_IRQ XPAR_FABRIC_AXI_DMA_0_MM2S_INTROUT_VEC_ID
#else
#error "Final BSP does not expose the axi_dma_0 MM2S interrupt macro"
#endif
#if defined(XPAR_FABRIC_AXI_DMA_0_S2MM_INTROUT_INTR)
#define EDZ_S2MM_IRQ XPAR_FABRIC_AXI_DMA_0_S2MM_INTROUT_INTR
#elif defined(XPAR_FABRIC_AXI_DMA_0_S2MM_INTROUT_VEC_ID)
#define EDZ_S2MM_IRQ XPAR_FABRIC_AXI_DMA_0_S2MM_INTROUT_VEC_ID
#else
#error "Final BSP does not expose the axi_dma_0 S2MM interrupt macro"
#endif
#if defined(XPAR_FABRIC_EDGEDET_TOP_0_INTERRUPT_INTR)
#define EDZ_ACCEL_IRQ XPAR_FABRIC_EDGEDET_TOP_0_INTERRUPT_INTR
#elif defined(XPAR_FABRIC_EDGEDET_TOP_0_INTERRUPT_VEC_ID)
#define EDZ_ACCEL_IRQ XPAR_FABRIC_EDGEDET_TOP_0_INTERRUPT_VEC_ID
#else
#error "Final BSP does not expose the edgedet_top_0 interrupt macro"
#endif

static XAxiDma dma;
/* AMD's standalone lwIP platform owns this instance. Keeping one shared GIC
 * preserves the GEM handlers installed before the accelerator/DMA handlers. */
extern XScuGic xInterruptController;
#define gic xInterruptController
static volatile int mm2s_done;
static volatile int s2mm_done;
static volatile int accelerator_done;
static volatile int dma_error;

static void dma_mm2s_isr(void *reference) {
    XAxiDma *instance = (XAxiDma *)reference;
    uint32_t status = XAxiDma_IntrGetIrq(instance, XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrAckIrq(instance, status, XAXIDMA_DMA_TO_DEVICE);
    if (status & XAXIDMA_IRQ_ERROR_MASK) dma_error = 1;
    if (status & XAXIDMA_IRQ_IOC_MASK) mm2s_done = 1;
}

static void dma_s2mm_isr(void *reference) {
    XAxiDma *instance = (XAxiDma *)reference;
    uint32_t status = XAxiDma_IntrGetIrq(instance, XAXIDMA_DEVICE_TO_DMA);
    XAxiDma_IntrAckIrq(instance, status, XAXIDMA_DEVICE_TO_DMA);
    if (status & XAXIDMA_IRQ_ERROR_MASK) dma_error = 1;
    if (status & XAXIDMA_IRQ_IOC_MASK) s2mm_done = 1;
}

static void accelerator_isr(void *reference) {
    (void)reference;
    Xil_Out32(EDZ_ACCELERATOR_ADDRESS + EDZ_CTRL_ISR, 1u);
    accelerator_done = 1;
}

static int connect_irq(uint32_t vector, Xil_InterruptHandler handler, void *reference) {
    int status = XScuGic_Connect(&gic, vector, handler, reference);
    if (status != XST_SUCCESS) return status;
    XScuGic_Enable(&gic, vector);
    return XST_SUCCESS;
}

int edz_board_init(void) {
    XAxiDma_Config *dma_config = XAxiDma_LookupConfig(XPAR_AXIDMA_0_DEVICE_ID);
    int status;
    if (!dma_config) return XST_FAILURE;
    status = XAxiDma_CfgInitialize(&dma, dma_config);
    if (status != XST_SUCCESS || XAxiDma_HasSg(&dma)) return XST_FAILURE;
    if (gic.IsReady != XIL_COMPONENT_IS_READY) return XST_FAILURE;
    status = connect_irq(EDZ_MM2S_IRQ, dma_mm2s_isr, &dma);
    if (status != XST_SUCCESS) return status;
    status = connect_irq(EDZ_S2MM_IRQ, dma_s2mm_isr, &dma);
    if (status != XST_SUCCESS) return status;
    status = connect_irq(EDZ_ACCEL_IRQ, accelerator_isr, NULL);
    if (status != XST_SUCCESS) return status;
    XAxiDma_IntrEnable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
    XAxiDma_IntrEnable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
    Xil_Out32(EDZ_ACCELERATOR_ADDRESS + EDZ_CTRL_GIE, 1u);
    Xil_Out32(EDZ_ACCELERATOR_ADDRESS + EDZ_CTRL_IER, 1u);
    return XST_SUCCESS;
}

void edz_board_recover(void) {
    XAxiDma_Reset(&dma);
    while (!XAxiDma_ResetIsDone(&dma)) { }
    mm2s_done = s2mm_done = accelerator_done = dma_error = 0;
}

int edz_board_infer(const uint8_t *rgb, size_t rgb_length, int16_t *output,
                    uint32_t timeout_ms, edz_board_stats_t *stats) {
    uint64_t *input_buffer = (uint64_t *)(uintptr_t)EDZ_INPUT_BUFFER_ADDRESS;
    int16_t *output_buffer = (int16_t *)(uintptr_t)EDZ_OUTPUT_BUFFER_ADDRESS;
    XTime start;
    XTime now;
    uint64_t timeout_ticks = ((uint64_t)COUNTS_PER_SECOND * timeout_ms) / 1000u;
    int status;
    if (!rgb || !output || rgb_length != EDZ_MAX_FRAME_PAYLOAD) return XST_INVALID_PARAM;
    if (edz_pack_axis_rgb(rgb, rgb_length, input_buffer) != 0) return XST_INVALID_PARAM;
    Xil_DCacheFlushRange((UINTPTR)input_buffer, EDZ_ACCEL_INPUT_BYTES);
    Xil_DCacheInvalidateRange((UINTPTR)output_buffer, EDZ_ACCELERATOR_OUTPUT_BYTES);
    mm2s_done = s2mm_done = accelerator_done = dma_error = 0;
    status = XAxiDma_SimpleTransfer(&dma, (UINTPTR)output_buffer,
            EDZ_ACCELERATOR_OUTPUT_BYTES, XAXIDMA_DEVICE_TO_DMA);
    if (status != XST_SUCCESS) return status;
    status = XAxiDma_SimpleTransfer(&dma, (UINTPTR)input_buffer,
            EDZ_ACCEL_INPUT_BYTES, XAXIDMA_DMA_TO_DEVICE);
    if (status != XST_SUCCESS) return status;
    XTime_GetTime(&start);
    Xil_Out32(EDZ_ACCELERATOR_ADDRESS + EDZ_CTRL_AP_CTRL, 1u);
    do {
        if (dma_error) {
            edz_board_recover();
            return XST_FAILURE;
        }
        XTime_GetTime(&now);
        if ((uint64_t)(now - start) > timeout_ticks) {
            edz_board_recover();
            return XST_DEVICE_BUSY;
        }
    } while (!mm2s_done || !s2mm_done || !accelerator_done);
    Xil_DCacheInvalidateRange((UINTPTR)output_buffer, EDZ_ACCELERATOR_OUTPUT_BYTES);
    memcpy(output, output_buffer, EDZ_ACCELERATOR_OUTPUT_BYTES);
    if (stats) {
        stats->kernel_cycles = ((uint64_t)(now - start) * UINT64_C(100000000)) /
                               COUNTS_PER_SECOND;
        stats->total_cycles = stats->kernel_cycles;
    }
    return XST_SUCCESS;
}
