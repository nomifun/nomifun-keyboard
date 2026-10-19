#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#define NK_SCREEN_WIDTH 428
#define NK_SCREEN_HEIGHT 142
typedef enum { NK_CONNECTING, NK_SLEEPING, NK_READY, NK_STARTING, NK_LISTENING, NK_RECOGNIZING, NK_POLISHING, NK_ERROR, NK_STATE_COUNT } nk_screen_state_t;
bool nk_screen_parse(const char *, nk_screen_state_t *);
const char *nk_screen_name(nk_screen_state_t);
void nk_screen_render(uint16_t *,nk_screen_state_t,uint32_t,int,uint32_t);
void nk_screen_render_strip(uint16_t *,nk_screen_state_t,uint32_t,int,uint32_t,int,int);
esp_err_t nk_screen_init(void);
bool nk_screen_available(void);
esp_err_t nk_screen_apply(nk_screen_state_t);
void nk_screen_key(unsigned);
uint32_t nk_screen_frames(void);
bool nk_screen_backlight(void);
uint32_t nk_screen_duty(void);
