idf_component_register(SRCS "vk_usb_native.c" "vk_usb_json.c" INCLUDE_DIRS "include"
    REQUIRES vk_input nk_screen esp_driver_gpio esp_driver_usb_serial_jtag esp_timer esp_hw_support)
