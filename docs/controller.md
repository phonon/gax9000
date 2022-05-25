# Controller App

## Concepts
There are three main state objects to run measurements:
1. **Global settings**: device X/Y size, die (x, y) id, etc.
2. **Programs**: The B1500 measurement program configuration (voltages, probe SMUs, etc.)
3. **Measurement Sweeps**: Type of measurement sweep (single, array, list of positions, etc.)

## User Profiles
User profiles cache and save all sweep parameters from the previous measurement run.
Typically these values either remain the same or are similar.