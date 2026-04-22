CC ?= cc
CFLAGS ?= -O3 -std=c17 -Wall -Wextra -Wpedantic
LDFLAGS ?=

TARGET := page_tiering_text_handler
SRC := main.c trace_parser.c summary_stats.c page_table.c numa_log.c median_estimator.c
OBJ := $(SRC:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(LDFLAGS)

clean:
	rm -f $(TARGET) $(OBJ)

.PHONY: all clean
