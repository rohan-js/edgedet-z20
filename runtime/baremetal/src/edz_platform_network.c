#if !defined(EDZ_XILINX_BAREMETAL)
#error "Build this source only in the Vitis standalone BSP"
#endif

#include "lwip/init.h"
#include "lwip/ip_addr.h"
#include "lwip/netif.h"
#include "lwip/timeouts.h"
#include "netif/xadapter.h"
#include "platform.h"
#include "platform_config.h"
#include "xstatus.h"

#ifndef EDZ_IP_A
#define EDZ_IP_A 192
#define EDZ_IP_B 168
#define EDZ_IP_C 1
#define EDZ_IP_D 10
#endif

static struct netif edz_netif;

int edz_platform_network_init(void) {
    ip_addr_t address;
    ip_addr_t netmask;
    ip_addr_t gateway;
    unsigned char mac[6] = {0x00u, 0x0Au, 0x35u, 0x00u, 0x01u, 0x20u};
    IP4_ADDR(&address, EDZ_IP_A, EDZ_IP_B, EDZ_IP_C, EDZ_IP_D);
    IP4_ADDR(&netmask, 255, 255, 255, 0);
    IP4_ADDR(&gateway, EDZ_IP_A, EDZ_IP_B, EDZ_IP_C, 1);
    if (!xemac_add(&edz_netif, &address, &netmask, &gateway, mac,
                   PLATFORM_EMAC_BASEADDR))
        return XST_FAILURE;
    netif_set_default(&edz_netif);
    netif_set_up(&edz_netif);
    platform_enable_interrupts();
    return XST_SUCCESS;
}

void edz_platform_network_poll(void) {
    xemacif_input(&edz_netif);
    sys_check_timeouts();
}
