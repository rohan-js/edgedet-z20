#if !defined(EDZ_XILINX_BAREMETAL)
#error "Build this entry point only in the Vitis standalone BSP"
#endif

#include "edz_board.h"
#include "edz_model_runtime.h"
#include "edz_tcp_server.h"

#if !EDZ_MODEL_PARAMETERS_PRESENT
#error "Bare-metal release requires the generated edz_model_runtime.h"
#endif

#include "lwip/init.h"
#include "platform.h"
#include "xil_printf.h"
#include "xstatus.h"

extern int edz_platform_network_init(void);
extern void edz_platform_network_poll(void);

int main(void) {
    init_platform();
    xil_printf("EdgeDet-Z20 standalone runtime\r\n");
    xil_printf("Model profile=%s crc32=%08x\r\n", EDZ_MODEL_PROFILE,
               (unsigned)EDZ_MODEL_CRC32);
    xil_printf("Hardware results require physical-board validation\r\n");
    lwip_init();
    if (edz_platform_network_init() != XST_SUCCESS) {
        xil_printf("ERROR: generated lwIP platform initialization failed\r\n");
        cleanup_platform();
        return 2;
    }
    if (edz_board_init() != XST_SUCCESS) {
        xil_printf("ERROR: accelerator/DMA/GIC initialization failed\r\n");
        cleanup_platform();
        return 1;
    }
    if (edz_tcp_server_start(5001u) != ERR_OK) {
        xil_printf("ERROR: TCP server initialization failed\r\n");
        cleanup_platform();
        return 3;
    }
    xil_printf("EDZ2 protocol v1 listening on TCP port 5001\r\n");
    for (;;) edz_platform_network_poll();
}
