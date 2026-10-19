#include "vk_usb.h"
#include "nk_screen.h"
volatile esp_err_t g_nk_usb_boot_error;
volatile esp_err_t g_nk_screen_boot_error;
void app_main(void) {
    g_nk_usb_boot_error=vk_usb_start();
    g_nk_screen_boot_error=nk_screen_init();
}
