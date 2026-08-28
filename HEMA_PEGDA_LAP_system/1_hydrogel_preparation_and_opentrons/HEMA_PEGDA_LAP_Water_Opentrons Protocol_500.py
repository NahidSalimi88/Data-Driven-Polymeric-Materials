from opentrons import protocol_api
from opentrons.protocol_api import SINGLE
from opentrons.types import Point

metadata = {
    'protocolName': 'HEMA PEGDA LAP, Preparation, 24 well plate',
    'author': 'Nahid (Optimized)',
    'description': 'Automated high-precision protocol for hydrogel screening in triplicate.'
}

requirements = {"robotType": "Flex", "apiLevel": "2.21"}

def run(protocol: protocol_api.ProtocolContext):

    # --- 1. SAMPLE MATRIX ---
    # Format: (Well, V_HEMA, V_PEG, V_Lap, V_WATER)
    muestras =  [
       
    ("A1", 224.95, 113.94, 127.00, 34.11),
    ("A2", 221.30, 129.13, 99.00, 50.58),
    ("A3", 204.60, 130.31, 27.50, 137.59),
    ("A4", 229.30, 133.06, 66.00, 71.64),
    ("A5", 201.85, 126.44, 132.50, 39.21),
    ("A6", 212.70, 121.25, 59.50, 106.55),
    ("B1", 215.60, 141.63, 108.00, 34.78),
    ("B2", 219.95, 112.56, 68.00, 99.49),
    ("B3", 257.60, 128.56, 34.50, 79.34),
    ("B4", 236.25, 144.81, 40.00, 78.94),
    ("B5", 205.90, 146.19, 81.00, 66.91),
    ("B6", 243.10, 146.75, 83.50, 26.65),
    ("C1", 258.55, 149.50, 47.00, 44.95),
    
    ]

    # --- 2. LABWARE SETUP ---
    trash = protocol.load_trash_bin("A3")
    tipracks = protocol.load_labware("opentrons_flex_96_tiprack_1000ul", "D3")
    res = protocol.load_labware("custom_4_reservoir_90000ul", "D2")
    res_lapeg = protocol.load_labware("19mlglass_15_tuberack_19000ul", "C2")
    h_s = protocol.load_module('heaterShakerModuleV1', 'D1') 
    plate = h_s.load_labware("corning_24_wellplate_3.4ml_flat")
    
    # --- 3. PIPETTE CONFIGURATION ---
    pipette = protocol.load_instrument("flex_8channel_1000", mount="left", tip_racks=[tipracks])
    pipette.configure_nozzle_layout(style=SINGLE, start="H1")

    # --- 4. SAFETY: LOCK LATCH ---
    h_s.close_labware_latch()
    
    # --- 5. REAGENT ASSIGNMENT ---
    agua = res['A1']
    hema = res_lapeg['B4']
    pegda_80 = res_lapeg['C2']
    lap = res_lapeg['A2']

       
    # Step 1: DISTRIBUCION DE AGUA
    protocol.comment("Distributing Agua...")
    pipette.flow_rate.aspirate = 80
    pipette.flow_rate.dispense = 60
    pipette.flow_rate.blow_out = 60
    
    pipette.pick_up_tip(tipracks['A1'])
    for well, v_hema, v_peg, v_lap, v_agua in muestras:
        pipette.aspirate(v_agua, agua.bottom(z=7))
        pipette.dispense(v_agua, plate[well].top(z=-8))
        dest_pared = plate[well].top(z=-12).move(Point(x=0, y=-7.5, z=0))
        pipette.move_to(dest_pared, speed=10) 
        pipette.blow_out(dest_pared)
        pipette.move_to(plate[well].top(z=10))
    pipette.drop_tip(trash)
    
    # Step 2: HEMA
    protocol.comment("Distributing HEMA...")
    pipette.flow_rate.aspirate = 60
    pipette.flow_rate.dispense = 60
    pipette.flow_rate.blow_out = 40
    
    pipette.pick_up_tip(tipracks['A2'])
    for well, v_hema, v_peg, v_lap, v_agua in muestras:
        pipette.aspirate(v_hema, hema.bottom(z=7))
        pipette.dispense(v_hema, plate[well].top(z=-8))
        dest_pared = plate[well].top(z=-12).move(Point(x=0, y=-7.5, z=0))
        pipette.move_to(dest_pared, speed=10) 
        pipette.blow_out(dest_pared)
        pipette.move_to(plate[well].top(z=10))
    pipette.drop_tip(trash)

    # --- POST-HEMA SHAKING ---
    protocol.comment("HEMA completed. Shaking composition at 200 RPM for 60 seconds...")
    h_s.set_and_wait_for_shake_speed(300)
    protocol.delay(seconds=60)
    h_s.deactivate_shaker()    

    # STEP 3: DISTRIBUTE PEGDA
    protocol.comment("Distributing PEGDA...")
    pipette.flow_rate.aspirate = 30 
    pipette.flow_rate.dispense = 30
    pipette.flow_rate.blow_out = 40
    
    pipette.pick_up_tip(tipracks['A3'])
    for well, v_hema, v_peg, v_lap, v_agua in muestras:
        pipette.aspirate(v_peg, pegda_80.bottom(z=7))
        protocol.delay(seconds=3) 
        pipette.move_to(pegda_80.top(z=5), speed=10)
        pipette.dispense(v_peg, plate[well].top(z=-8))
        dest_pared = plate[well].top(z=-12).move(Point(x=0, y=-7.5, z=0))
        pipette.move_to(dest_pared, speed=10) 
        pipette.blow_out(dest_pared)
        pipette.move_to(plate[well].top(z=10))
    pipette.drop_tip(trash)

    # --- POST-PEGDA SHAKING ---
    protocol.comment("PEGDA completed. Shaking composition at 200 RPM for 60 seconds...")
    h_s.set_and_wait_for_shake_speed(300)
    protocol.delay(seconds=60)
    h_s.deactivate_shaker()
    
 # STEP 4: DISTRIBUTE Lap
    protocol.comment("Distributing LAP...")
    pipette.flow_rate.aspirate = 80
    pipette.flow_rate.dispense = 40
    pipette.flow_rate.blow_out = 30
    
    pipette.pick_up_tip(tipracks['A4'])
    for well, v_hema, v_peg, v_lap, v_agua in muestras:
        pipette.aspirate(v_lap, lap.bottom(z=4))
        protocol.delay(seconds=2) 
        pipette.move_to(lap.top(z=5), speed=10)
        pipette.dispense(v_lap, plate[well].top(z=-8))
        dest_pared = plate[well].top(z=-12).move(Point(x=0, y=-7.5, z=0))
        pipette.move_to(dest_pared, speed=10) 
        pipette.blow_out(dest_pared)
        pipette.move_to(plate[well].top(z=10))
    pipette.drop_tip(trash)
       
        
    # --- 6. COMPLETION & MIXING ---
    protocol.comment("Starting plate shaking...")
    h_s.set_and_wait_for_shake_speed(500)
    protocol.delay(minutes=10)
    h_s.deactivate_shaker()
    h_s.open_labware_latch()
    protocol.comment("Protocol completed successfully.")