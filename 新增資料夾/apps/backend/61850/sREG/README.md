# MMS Server SREG Module

This project contains the source file `mms_server_sreg.c`, which implements the **SREG auxiliary service product** for the Taiwan Power Company (Taipower) trading platform.

## Overview
- **Language**: C
- **Purpose**: Provides support for SREG functions within the MMS server environment.
- **Context**: Designed as part of Taipower’s trading platform auxiliary services.

## Features
- Implements SREG auxiliary service logic.
- Integrates with MMS server modules.
- Provides extensible structure for future enhancements.

## Additional Component
- **`TPC_SREG_20260505_ASG90004_Taipower.cid`**  
  - Written in **XML format**.  
  - Conforms to the **IEC 61850 SREG specification**.  
  - Defines configuration and data exchange rules for the SREG auxiliary service product.  

## Usage
1. Clone the repository.
2. Use `TPC_SREG_20260505_ASG90004_Taipower.cid` as the XML configuration file to ensure compliance with IEC 61850 SREG spec, and compile the source file with your preferred C compiler.
3. Deploy within the MMS server environment. 
