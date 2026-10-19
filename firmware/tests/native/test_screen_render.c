#include "nk_screen.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char**argv){
 size_t count=NK_SCREEN_WIDTH*NK_SCREEN_HEIGHT;uint16_t*base=calloc(count+2U,sizeof(uint16_t));assert(base);base[0]=0xcafe;base[count+1U]=0xbeef;uint16_t*p=base+1U;
 for(unsigned s=0;s<NK_STATE_COUNT;s++){nk_screen_state_t parsed;assert(nk_screen_parse(nk_screen_name((nk_screen_state_t)s),&parsed)&&parsed==(nk_screen_state_t)s);nk_screen_render(p,parsed,1240U,3,120U);assert(base[0]==0xcafe&&base[count+1U]==0xbeef);unsigned changed=0;for(size_t i=0;i<count;i++)changed+=p[i]!=0x0843;assert(changed>2000U&&changed<count/2U);uint16_t tile[NK_SCREEN_WIDTH*8U];for(int row=0;row<NK_SCREEN_HEIGHT;row+=8){int rows=NK_SCREEN_HEIGHT-row;if(rows>8)rows=8;nk_screen_render_strip(tile,parsed,1240U,3,120U,row,rows);assert(memcmp(tile,p+row*NK_SCREEN_WIDTH,(size_t)rows*NK_SCREEN_WIDTH*2U)==0);}if(argc>1){char path[512];snprintf(path,sizeof(path),"%s/%s.rgb565",argv[1],nk_screen_name(parsed));FILE*f=fopen(path,"wb");assert(f);assert(fwrite(p,2U,count,f)==count);fclose(f);}}
 nk_screen_state_t state;assert(!nk_screen_parse("private subtitle text",&state));free(base);puts("actual framebuffer render bounds/status-only/glyph/key-feedback tests passed");return 0;
}

