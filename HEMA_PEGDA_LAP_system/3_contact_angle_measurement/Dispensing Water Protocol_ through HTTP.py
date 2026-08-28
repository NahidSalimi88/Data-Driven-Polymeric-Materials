from opentrons import protocol_api
from opentrons.protocol_api import SINGLE
from opentrons.types import Point
import os
import time

metadata = {
    'protocolName': 'HTTP-Server Handshake Multi-Dispensing',
    'author': 'Nahid',
    'description': 'Water droplet multi-dispensing utilizing internal web flags.',
}

requirements = {"robotType": "Flex", "apiLevel": "2.21"}

def run(protocol: protocol_api.ProtocolContext):
    # Flag file path to communicate with the imaging script
    TARGET_FLAG_PATH = "/var/lib/jupyter/notebooks/drop.txt" 

    Samples = [("C1", 6)]

    # --- LABWARE SELECTION ---
    trash = protocol.load_trash_bin("A3")
    tipracks = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "D3")
    res = protocol.load_labware("custom_4_reservoir_90000ul", "D2")
    res_light = protocol.load_labware("custom_4_reservoir_5000ul", "B2")
    res_motor = protocol.load_labware("19mlglass_15_tuberack_19000ul", "A1")
    plate = protocol.load_labware("corning_24_wellplate_3.4ml_flat", "B1")

    # --- PIPETTE CONFIGURATION ---
    pipette = protocol.load_instrument("flex_8channel_1000", mount="left", tip_racks=[tipracks])
    pipette.configure_nozzle_layout(style=SINGLE, start="H1")
    water = res['A1']

    # --- EXECUTION ---
    protocol.comment("Beginning automated internal-handshake array run...")
    pipette.flow_rate.aspirate = 40
    pipette.flow_rate.dispense = 10
    pipette.pick_up_tip(tipracks['A1'])

    well, v_water = Samples[0]
    
    # Clean out any old flag before starting
    if not protocol.is_simulating() and os.path.exists(TARGET_FLAG_PATH):
        os.remove(TARGET_FLAG_PATH)
    
    # Volume configuration for bulk aspiration
    BULK_ASPIRATE_VOL = 100
    current_volume = 0  # Track remaining volume in the tip

    for i in range(100):
        protocol.comment(f"Dispensing droplet {i+1}/24...")
        
        # 1. Refill 100 uL only if remaining volume is less than required droplet volume
        if current_volume < v_water:
            protocol.comment(f"Aspirating {BULK_ASPIRATE_VOL} uL of water...")
            pipette.aspirate(BULK_ASPIRATE_VOL, water.bottom(z=10))
            current_volume = BULK_ASPIRATE_VOL
            protocol.delay(seconds=1)

        # 2. Move to sample location and dispense 6 uL
        pipette.move_to(plate[well].top(z=70), speed=50)
        target_position = plate[well].top(z=48).move(Point(x=-1.5, y=-0.8, z=0))
        
        pipette.dispense(v_water, target_position)
        current_volume -= v_water  # Deduct dispensed amount from current tracking
        
        protocol.delay(seconds=0.5)
        pipette.move_to(plate[well].top(z=70), speed=30)
        
        # --- THE INTERNAL SYSTEM HANDSHAKE (CAMERA / PC INTERFACE) ---
        if not protocol.is_simulating():
            protocol.comment("Publishing drop flag to internal web server...")
            with open(TARGET_FLAG_PATH, "w") as f:
                f.write("DROP_DONE")
                
            protocol.comment("Flag live. Waiting for PC to capture photo...")
            time.sleep(3)
            
            # Clear flag after photo capture delay
            if os.path.exists(TARGET_FLAG_PATH):
                os.remove(TARGET_FLAG_PATH)
                
            protocol.comment("Advancing to next sequence iteration...")
            time.sleep(2)
        else:
            protocol.delay(seconds=1)
        
    # Dispense remaining water back to reservoir if needed, then drop tip
    if current_volume > 0:
        pipette.dispense(current_volume, water.top(z=2))
        
    pipette.drop_tip(trash)