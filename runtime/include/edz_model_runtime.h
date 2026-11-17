#ifndef EDZ_MODEL_RUNTIME_H
#define EDZ_MODEL_RUNTIME_H

/* Host-test fallback. A trained export replaces this file in the Vitis stage. */
#define EDZ_MODEL_PARAMETERS_PRESENT 0
#define EDZ_MODEL_CRC32 0u
#define EDZ_MODEL_PROFILE "untrained-fallback"
#define EDZ_MODEL_OUTPUT_SCALE (1.0f / 256.0f)

#endif
