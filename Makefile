CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=c11
LDFLAGS ?=

BUILD := build
SRC := src

PHASES := phase1_baseline phase3_no_cache phase4_no_store phase5_alu_contention
BINS := $(addprefix $(BUILD)/,$(PHASES))

.PHONY: all clean

all: $(BINS)

$(BUILD)/%: $(SRC)/%.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD)
