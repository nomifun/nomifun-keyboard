idf_component_register(SRCS "nk_screen_render.c" "nk_screen_panel.c" INCLUDE_DIRS "include"
    REQUIRES esp_driver_gpio esp_driver_spi esp_driver_ledc esp_timer heap)
