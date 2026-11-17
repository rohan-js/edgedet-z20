#if !defined(EDZ_XILINX_BAREMETAL)
#error "Build this source only in the Vitis standalone BSP"
#endif

#include "edz_tcp_server.h"

#include "edz_board.h"
#include "edz_postprocess.h"
#include "edz_protocol.h"
#include "lwip/ip_addr.h"
#include "lwip/pbuf.h"
#include "lwip/tcp.h"
#include "xstatus.h"

#include <string.h>

#define EDZ_SERVER_PORT 5001u
#define EDZ_FRAME_RING_SIZE 2u
#define EDZ_INFERENCE_TIMEOUT_MS 500u

typedef struct {
    struct tcp_pcb *pcb;
    uint8_t header_wire[EDZ_REQUEST_HEADER_SIZE];
    edz_request_header_t header;
    size_t header_received;
    size_t payload_received;
    unsigned ring_index;
} connection_t;

static connection_t connection;
static uint8_t frame_ring[EDZ_FRAME_RING_SIZE][EDZ_MAX_FRAME_PAYLOAD]
    __attribute__((aligned(64), section(".ddr_buffers")));
static int16_t tensor[EDZ_HEAD_VALUE_COUNT]
    __attribute__((aligned(64), section(".ddr_buffers")));
static uint8_t response_payload[EDZ_MAX_DETECTIONS * EDZ_DETECTION_WIRE_SIZE];
static uint32_t dropped_frames;

static void reset_message(connection_t *state) {
    state->header_received = 0u;
    state->payload_received = 0u;
    memset(&state->header, 0, sizeof(state->header));
}

static err_t send_response(struct tcp_pcb *pcb, uint16_t status, uint32_t frame_id,
                           uint64_t kernel_cycles, uint64_t total_cycles,
                           const edz_detection_t *detections, size_t count) {
    edz_response_header_t header;
    uint8_t header_wire[EDZ_RESPONSE_HEADER_SIZE];
    size_t index;
    size_t payload_length;
    err_t result;
    if (count > EDZ_MAX_DETECTIONS) count = EDZ_MAX_DETECTIONS;
    payload_length = count * EDZ_DETECTION_WIRE_SIZE;
    for (index = 0u; index < count; ++index)
        edz_encode_detection(detections + index,
                             response_payload + index * EDZ_DETECTION_WIRE_SIZE);
    memset(&header, 0, sizeof(header));
    header.version = EDZ_PROTOCOL_VERSION;
    header.status = status;
    header.frame_id = frame_id;
    header.kernel_cycles = kernel_cycles;
    header.total_cycles = total_cycles;
    header.detection_count = (uint16_t)count;
    header.dropped_frames = dropped_frames;
    header.payload_length = (uint32_t)payload_length;
    edz_encode_response_header(&header, header_wire);
    header.crc32 = edz_response_crc(header_wire, response_payload, payload_length);
    edz_encode_response_header(&header, header_wire);
    if (tcp_sndbuf(pcb) < EDZ_RESPONSE_HEADER_SIZE + payload_length) return ERR_MEM;
    result = tcp_write(pcb, header_wire, EDZ_RESPONSE_HEADER_SIZE, TCP_WRITE_FLAG_COPY);
    if (result != ERR_OK) return result;
    if (payload_length != 0u) {
        result = tcp_write(pcb, response_payload, (u16_t)payload_length,
                           TCP_WRITE_FLAG_COPY);
        if (result != ERR_OK) return result;
    }
    return tcp_output(pcb);
}

static err_t process_frame(connection_t *state) {
    uint8_t *frame = frame_ring[state->ring_index];
    edz_board_stats_t stats;
    edz_detection_t detections[EDZ_MAX_DETECTIONS];
    edz_decode_config_t config = edz_default_decode_config();
    size_t count;
    int status;
    uint32_t crc = edz_request_crc(state->header_wire, frame,
                                   state->header.payload_length);
    if (crc != state->header.crc32) {
        ++dropped_frames;
        return send_response(state->pcb, EDZ_STATUS_BAD_CRC, state->header.frame_id,
                             0u, 0u, NULL, 0u);
    }
    status = edz_board_infer(frame, state->header.payload_length, tensor,
                             EDZ_INFERENCE_TIMEOUT_MS, &stats);
    if (status == XST_DEVICE_BUSY) {
        ++dropped_frames;
        return send_response(state->pcb, EDZ_STATUS_ACCELERATOR_TIMEOUT,
                             state->header.frame_id, 0u, 0u, NULL, 0u);
    }
    if (status != XST_SUCCESS) {
        ++dropped_frames;
        return send_response(state->pcb, EDZ_STATUS_DMA_ERROR,
                             state->header.frame_id, 0u, 0u, NULL, 0u);
    }
    count = edz_decode_and_nms(tensor, &config, detections);
    state->ring_index = (state->ring_index + 1u) % EDZ_FRAME_RING_SIZE;
    return send_response(state->pcb, EDZ_STATUS_OK, state->header.frame_id,
                         stats.kernel_cycles, stats.total_cycles, detections, count);
}

static err_t consume_bytes(connection_t *state, const uint8_t *data, size_t length) {
    while (length != 0u) {
        if (state->header_received < EDZ_REQUEST_HEADER_SIZE) {
            size_t needed = EDZ_REQUEST_HEADER_SIZE - state->header_received;
            size_t take = length < needed ? length : needed;
            memcpy(state->header_wire + state->header_received, data, take);
            state->header_received += take;
            data += take;
            length -= take;
            if (state->header_received == EDZ_REQUEST_HEADER_SIZE) {
                int decode_status = edz_decode_request_header(state->header_wire,
                                                              &state->header);
                edz_status_t validation;
                if (decode_status != 0) return (err_t)ERR_VAL;
                validation = edz_validate_request(&state->header);
                if (validation != EDZ_STATUS_OK) {
                    ++dropped_frames;
                    send_response(state->pcb, (uint16_t)validation,
                                  state->header.frame_id, 0u, 0u, NULL, 0u);
                    return ERR_VAL; /* Close: payload length cannot be trusted/resynced. */
                }
            }
        } else {
            size_t needed = state->header.payload_length - state->payload_received;
            size_t take = length < needed ? length : needed;
            memcpy(frame_ring[state->ring_index] + state->payload_received, data, take);
            state->payload_received += take;
            data += take;
            length -= take;
            if (state->payload_received == state->header.payload_length) {
                err_t result = process_frame(state);
                reset_message(state);
                if (result != ERR_OK) return result;
            }
        }
    }
    return ERR_OK;
}

static void connection_error(void *arg, err_t error) {
    connection_t *state = (connection_t *)arg;
    (void)error;
    if (state) {
        state->pcb = NULL;
        reset_message(state);
    }
}

static err_t receive_data(void *arg, struct tcp_pcb *pcb, struct pbuf *p, err_t error) {
    connection_t *state = (connection_t *)arg;
    struct pbuf *segment;
    err_t result = error;
    if (!p) {
        tcp_close(pcb);
        state->pcb = NULL;
        reset_message(state);
        return ERR_OK;
    }
    if (error == ERR_OK) {
        result = ERR_OK;
        for (segment = p; segment && result == ERR_OK; segment = segment->next)
            result = consume_bytes(state, (const uint8_t *)segment->payload, segment->len);
        tcp_recved(pcb, p->tot_len);
    }
    pbuf_free(p);
    if (result != ERR_OK) {
        tcp_arg(pcb, NULL);
        tcp_recv(pcb, NULL);
        tcp_err(pcb, NULL);
        tcp_close(pcb);
        state->pcb = NULL;
        reset_message(state);
        return ERR_OK;
    }
    return ERR_OK;
}

static err_t accept_connection(void *arg, struct tcp_pcb *new_pcb, err_t error) {
    (void)arg;
    if (error != ERR_OK) return error;
    if (connection.pcb != NULL) {
        ++dropped_frames;
        tcp_abort(new_pcb);
        return ERR_ABRT;
    }
    memset(&connection, 0, sizeof(connection));
    connection.pcb = new_pcb;
    tcp_arg(new_pcb, &connection);
    tcp_recv(new_pcb, receive_data);
    tcp_err(new_pcb, connection_error);
    tcp_nagle_disable(new_pcb);
    return ERR_OK;
}

err_t edz_tcp_server_start(unsigned short port) {
    struct tcp_pcb *pcb = tcp_new_ip_type(IPADDR_TYPE_ANY);
    err_t result;
    if (!pcb) return ERR_MEM;
    if (port == 0u) port = EDZ_SERVER_PORT;
    result = tcp_bind(pcb, IP_ANY_TYPE, port);
    if (result != ERR_OK) {
        tcp_close(pcb);
        return result;
    }
    pcb = tcp_listen_with_backlog(pcb, 1u);
    if (!pcb) return ERR_MEM;
    tcp_accept(pcb, accept_connection);
    return ERR_OK;
}
