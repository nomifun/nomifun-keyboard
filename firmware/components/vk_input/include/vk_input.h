#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    VK_INPUT_KEY_K1 = 0,
    VK_INPUT_KEY_K2,
    VK_INPUT_KEY_K3,
    VK_INPUT_KEY_K4,
} vk_input_key_t;

typedef enum {
    VK_INPUT_TRANSITION_DOWN = 0,
    VK_INPUT_TRANSITION_UP,
    VK_INPUT_TRANSITION_CLICK,
} vk_input_transition_kind_t;

typedef struct {
    vk_input_transition_kind_t kind;
    vk_input_key_t key;
    uint32_t duration_ms;
} vk_input_transition_t;

typedef struct {
    bool stable_pressed;
    bool candidate_pressed;
    uint8_t candidate_count;
    bool armed;
    uint32_t down_ms;
} vk_input_debounce_key_t;

typedef struct {
    vk_input_debounce_key_t keys[4];
} vk_input_debounce_t;

void vk_input_debounce_reset(vk_input_debounce_t *state);
size_t vk_input_debounce_sample(vk_input_debounce_t *state,
                                uint8_t pressed_mask,
                                uint32_t now_ms,
                                vk_input_transition_t *output,
                                size_t capacity);

#ifdef __cplusplus
}
#endif
