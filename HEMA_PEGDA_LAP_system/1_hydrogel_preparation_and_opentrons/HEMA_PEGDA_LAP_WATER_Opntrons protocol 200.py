from opentrons import protocol_api
from opentrons.protocol_api import SINGLE
from opentrons.types import Point

metadata = {
    'protocolName': 'HEMA, PEGDA Dual_LAp Prep (Dual-LAP Stock System)',
    'author': 'Nahid',
    'description': 'Automated 96-well hydrogel protocol with dynamic 1% and 2% LAP stock selection and in-well mixing.'
}

requirements = {"robotType": "Flex", "apiLevel": "2.21"}

def run(protocol: protocol_api.ProtocolContext):

    # --- 1. FULL 96-WELL SAMPLE MATRIX ---
    # Format: (Well, V_HEMA, V_PEG, V_LAP, V_WATER, use_stock_2)
    # use_stock_2: False -> Stock 1% (lap_stock_1), True -> Stock 2% (lap_stock_2)
    muestras = [
        # --- ROW A ---
        ("A1", 86.24, 56.65, 43.2, 13.91, False),
        ("A2", 94.50, 57.93, 16.00, 18.15, False),
        ("A3", 94.22, 48.20, 32.28, 25.30, True),
        ("A4", 93.38, 46.08, 26.74, 29.80, True),
        ("A5", 86.98, 46.83, 28.62, 34.34, True),
        ("A6", 95.90, 54.65, 28.40, 21.05, True),
        ("A7", 85.08, 48.50, 23.60, 22.82, False),
        ("A8", 80.94, 47.35, 36.60, 25.11, False),
        ("A9", 103.42, 59.80, 18.80, 18.06, False),
        ("A10", 100.42, 56.90, 35.20, 7.48, True),
        ("A11", 89.44, 49.78, 44.10, 16.68, True),
        ("A12", 93.38, 46.08, 26.74, 29.80, True),

        # --- ROW B ---
        ("B1", 89.98, 45.58, 50.80, 13.64, False),
        ("B2", 88.52, 51.65, 39.60, 20.23, False),
        ("B3", 92.46, 49.55, 39.30, 18.69, True),
        ("B4", 81.84, 52.13, 11.00, 55.03, False),
        ("B5", 91.16, 59.30, 42.60, 6.94, True),
        ("B6", 84.08, 52.83, 47.10, 15.99, True),
        ("B7", 80.94, 47.35, 36.60, 25.11, False),
        ("B8", 100.42, 56.90, 35.20, 7.48, True),
        ("B9", 101.92, 56.15, 22.60, 19.33, True),
        ("B10", 95.42, 55.15, 29.00, 20.43, True),
        ("B11", 95.90, 54.65, 32.70, 16.75, True),
        ("B12", 88.52, 51.65, 39.60, 20.23, False),

        # --- ROW C ---
        ("C1", 82.36, 58.48, 32.40, 26.76, False),
        ("C2", 94.22, 48.20, 40.60, 16.98, True),
        ("C3", 87.98, 45.03, 27.20, 39.79, False),
        ("C4", 91.72, 53.23, 26.40, 28.65, False),
        ("C5", 94.50, 57.93, 16.00, 31.57, False),
        ("C6", 101.42, 53.80, 28.30, 16.48, True),
        ("C7", 80.74, 50.58, 53.00, 15.68, False),
        ("C8", 101.92, 56.15, 22.60, 19.33, True),
        ("C9", 85.38, 54.08, 30.70, 29.84, True),
        ("C10", 85.08, 48.50, 23.80, 42.62, False),
        ("C11", 91.16, 59.30, 42.60, 6.94, True),
        ("C12", 97.24, 58.70, 33.40, 10.66, False),

        # --- ROW D ---
        ("D1", 95.42, 55.15, 29.00, 20.43, True),
        ("D2", 86.24, 56.65, 43.20, 13.91, False),
        ("D3", 95.90, 54.65, 32.70, 16.75, True),
        ("D4", 98.92, 55.43, 38.60, 7.05, True),
        ("D5", 87.98, 45.03, 27.20, 39.79, False),
        ("D6", 103.42, 59.80, 18.80, 18.06, False),
        ("D7", 89.44, 49.78, 44.10, 16.68, True),
        ("D8", 97.58, 49.15, 49.80, 3.47, True),
        ("D9", 98.22, 47.20, 47.00, 7.58, False),
        ("D10", 103.04, 51.43, 13.80, 31.73, False),
        ("D11", 83.40, 51.03, 47.90, 17.67, True),
        ("D12", 94.50, 57.93, 16.00, 31.57, False),

        # --- ROW E ---
        ("E1", 82.36, 58.48, 32.40, 26.76, False),
        ("E2", 95.42, 55.15, 29.00, 20.43, True),
        ("E3", 97.24, 58.70, 33.40, 10.66, False),
        ("E4", 85.38, 54.08, 30.70, 29.84, True),
        ("E5", 101.92, 56.15, 22.60, 19.33, True),
        ("E6", 91.72, 53.23, 26.40, 28.65, False),
        ("E7", 85.38, 54.08, 30.70, 29.84, True),
        ("E8", 93.38, 46.08, 33.90, 26.64, True),
        ("E9", 88.52, 51.65, 39.60, 20.23, False),
        ("E10", 96.22, 57.43, 45.00, 1.36, True),
        ("E11", 82.36, 58.48, 32.40, 26.76, False),
        ("E12", 92.46, 49.55, 39.30, 18.69, True),

        # --- ROW F ---
        ("F1", 84.08, 52.83, 47.10, 15.99, True),
        ("F2", 91.72, 53.23, 26.40, 28.65, False),
        ("F3", 89.98, 45.58, 50.80, 13.64, False),
        ("F4", 86.98, 46.83, 36.00, 30.19, True),
        ("F5", 101.42, 53.80, 28.30, 16.48, True),
        ("F6", 98.92, 55.43, 38.60, 7.05, True),
        ("F7", 103.04, 51.43, 13.80, 31.73, False),   
        ("F8", 83.40, 51.03, 47.90, 17.67, True),
        ("F9", 91.16, 59.30, 42.60, 6.94, True),
        ("F10", 94.22, 48.20, 40.60, 16.98, True),
        ("F11", 81.84, 52.13, 11.00, 55.03, False),
        ("F12", 86.24, 56.65, 43.20, 13.91, False),

        # --- ROW G ---
        ("G1", 97.58, 49.15, 49.80, 3.47, True),
        ("G2", 80.74, 50.58, 53.00, 15.68, False),
        ("G3", 103.42, 59.80, 18.80, 18.06, False),
        ("G4", 81.84, 52.13, 11.00, 55.03, False),
        ("G5", 89.44, 49.78, 44.10, 16.68, True),
        ("G6", 92.46, 49.55, 39.30, 18.69, True),
        ("G7", 97.24, 58.70, 33.40, 10.66, False),
        ("G8", 85.08, 48.50, 23.80, 42.62, False),
        ("G9", 83.40, 51.03, 47.90, 17.67, True),
        ("G10", 86.98, 46.83, 36.00, 30.19, True),
        ("G11", 96.22, 57.43, 45.00, 1.36, True),
        ("G12", 100.42, 56.90, 35.20, 7.48, True),

        # --- ROW H ---
        ("H1", 98.92, 55.43, 38.60, 7.05, True),
        ("H2", 101.42, 53.80, 28.30, 16.48, True),
        ("H3", 98.22, 47.20, 47.00, 7.58, False),
        ("H4", 80.94, 47.35, 36.60, 35.11, False),
        ("H5", 84.08, 52.83, 47.10, 15.99, True),
        ("H6", 89.98, 45.58, 50.80, 13.64, False),
        ("H7", 96.22, 57.43, 45.00, 1.36, True),
        ("H8", 80.74, 50.58, 53.00, 15.68, False),
        ("H9", 87.98, 45.03, 27.20, 39.79, False),
        ("H10", 98.22, 47.20, 47.00, 7.58, False),
        ("H11", 103.04, 51.43, 13.80, 31.73, False),
        ("H12", 97.58, 49.15, 49.80, 3.47, True)

    ]

    # --- 2. LABWARE SETUP ---
    trash = protocol.load_trash_bin("A3")
    tipracks = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "D3")
    res = protocol.load_labware("custom_4_reservoir_90000ul", "D2")
    res_lapeg = protocol.load_labware("19mlglass_15_tuberack_19000ul", "B2")
    h_s = protocol.load_module('heaterShakerModuleV1', 'D1') 
    plate = h_s.load_labware("corning_96_wellplate_360ul_flat")
    
    # --- 3. PIPETTE CONFIGURATION ---
    pipette = protocol.load_instrument("flex_8channel_1000", mount="left", tip_racks=[tipracks])
    pipette.configure_nozzle_layout(style=SINGLE, start="H1")

    # --- 4. SAFETY: LOCK LATCH ---
    h_s.close_labware_latch()
    
    # --- 5. REAGENT ASSIGNMENT ---
    agua = res['A1']
    hema = res_lapeg['B4']
    pegda_80 = res_lapeg['C2']
    lap_stock_1 = res_lapeg['A2']  
    lap_stock_2 = res_lapeg['A3']  

  

   # STEP 1: DISTRIBUTE WATER
    protocol.comment("Distributing Water...")
    pipette.flow_rate.aspirate = 80
    pipette.flow_rate.dispense = 50
    pipette.flow_rate.blow_out = 60
    
    pipette.pick_up_tip(tipracks['A1'])
    for well, v_hema, v_peg, v_lap, v_agua, use_stock_2 in muestras:
        if v_agua > 0:
            pipette.aspirate(v_agua, agua.bottom(z=3))
            pipette.dispense(v_agua, plate[well].top(z=-2))
            dest_pared = plate[well].top(z=-3).move(Point(x=0, y=-2.5, z=0))
            pipette.move_to(dest_pared, speed=10) 
            pipette.blow_out(dest_pared)
            pipette.move_to(plate[well].top(z=10))
    pipette.drop_tip(trash)

    # STEP 2: DISTRIBUTE HEMA
    protocol.comment("Distributing HEMA...")
    pipette.flow_rate.aspirate = 50
    pipette.flow_rate.dispense = 30
    pipette.flow_rate.blow_out = 40
    
    pipette.pick_up_tip(tipracks['A2'])
    for well, v_hema, v_peg, v_lap, v_agua, use_stock_2 in muestras:
        pipette.aspirate(v_hema, hema.bottom(z=5))
        protocol.delay(seconds=2) 
        pipette.move_to(hema.top(z=5), speed=10)
        pipette.dispense(v_hema, plate[well].top(z=-2))
        dest_pared = plate[well].top(z=-3).move(Point(x=0, y=-2.5, z=0))
        pipette.move_to(dest_pared, speed=10) 
        pipette.blow_out(dest_pared)
        pipette.move_to(plate[well].top(z=10))
    pipette.drop_tip(trash)

 # STEP 3: DISTRIBUTE PEGDA (80% Stock)
    protocol.comment("Distributing PEGDA...")
    pipette.flow_rate.aspirate = 30 
    pipette.flow_rate.dispense = 30
    pipette.flow_rate.blow_out = 40
    
    pipette.pick_up_tip(tipracks['A3'])
    for well, v_hema, v_peg, v_lap, v_agua, use_stock_2 in muestras:
        pipette.aspirate(v_peg, pegda_80.bottom(z=8))
        protocol.delay(seconds=3) 
        pipette.move_to(pegda_80.top(z=5), speed=10)
        pipette.dispense(v_peg, plate[well].top(z=-2))
        dest_pared = plate[well].top(z=-3).move(Point(x=0, y=-2.5, z=0))
        pipette.move_to(dest_pared, speed=10) 
        pipette.blow_out(dest_pared)
        pipette.move_to(plate[well].top(z=10))
    pipette.drop_tip(trash)
    
    # STEP 4: DISTRIBUTE LAP & IN-WELL MIXING (SEPARATED BY STOCK CONCENTRATION)
    protocol.comment("Distributing LAP Stock 1% and Stock 2% with separate tips to prevent contamination...")
    
    pipette.flow_rate.aspirate = 50
    pipette.flow_rate.dispense = 40
    pipette.flow_rate.blow_out = 60

    # --- SUB-STEP 4A: PROCESS LAP STOCK 1% (use_stock_2 == False) ---
    protocol.comment("Processing LAP Stock 1% (False samples)...")
    pipette.pick_up_tip(tipracks['A4'])
    
    for well, v_hema, v_peg, v_lap, v_agua, use_stock_2 in muestras:
        if not use_stock_2:  # False (Stock 1%)
            pipette.aspirate(v_lap, lap_stock_1.bottom(z=6))
            protocol.delay(seconds=2) 
            pipette.move_to(lap_stock_1.top(z=5), speed=10)
            pipette.dispense(v_lap, plate[well].top(z=-2))

            # In-Well Mixing
            pipette.flow_rate.aspirate = 60
            pipette.flow_rate.dispense = 60
            for _ in range(3):
                pipette.aspirate(120, plate[well].bottom(z=1))
                pipette.dispense(80, plate[well].bottom(z=4))
                
            dest_pared = plate[well].top(z=-2).move(Point(x=0, y=-2.5, z=0))
            pipette.move_to(dest_pared, speed=10) 
            pipette.blow_out(dest_pared)
            pipette.move_to(plate[well].top(z=10))
            
            # Reset flow rates for next aspirate
            pipette.flow_rate.aspirate = 50
            pipette.flow_rate.dispense = 40

    pipette.drop_tip(trash)  

    # --- SUB-STEP 4B: PROCESS LAP STOCK 2% (use_stock_2 == True) ---
    protocol.comment("Processing LAP Stock 2% (True samples)...")
    pipette.pick_up_tip(tipracks['A5'])  
    
    for well, v_hema, v_peg, v_lap, v_agua, use_stock_2 in muestras:
        if use_stock_2:  # True (Stock 2%)
            pipette.aspirate(v_lap, lap_stock_2.bottom(z=4))
            protocol.delay(seconds=2) 
            pipette.move_to(lap_stock_2.top(z=5), speed=10)
            pipette.dispense(v_lap, plate[well].top(z=-2))

            # In-Well Mixing
            pipette.flow_rate.aspirate = 60
            pipette.flow_rate.dispense = 60
            for _ in range(3):
                pipette.aspirate(120, plate[well].bottom(z=1))
                pipette.dispense(80, plate[well].bottom(z=4))
                
            dest_pared = plate[well].top(z=-2).move(Point(x=0, y=-2.5, z=0))
            pipette.move_to(dest_pared, speed=10) 
            pipette.blow_out(dest_pared)
            pipette.move_to(plate[well].top(z=10))
            
            # Reset flow rates for next aspirate
            pipette.flow_rate.aspirate = 50
            pipette.flow_rate.dispense = 40

    pipette.drop_tip(trash)
        
    # --- 6. COMPLETION & MIXING (SHAKER) ---
    protocol.comment("Starting plate shaking (10 min at 1000 RPM)...")
    h_s.set_and_wait_for_shake_speed(500)
    protocol.delay(minutes=10)
    h_s.deactivate_shaker()
    h_s.open_labware_latch()
    protocol.comment("Protocol completed successfully.")