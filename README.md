# Digitally Traceable Workflow for Synthesis and Characterization of Hydrogel Networks
## A Data-Driven Framework for HEMA/PEGDA/LAP Formulations

This repository contains the complete experimental pipeline, automation protocols, and data processing scripts developed for the synthesis and characterization of HEMA/PEGDA/LAP hydrogel networks. The workflow integrates digital Experimental Design (DoE), robotic liquid handling, automated contact-angle analysis, indentation-based mechanical testing, and Python-based cross-property analysis into a single, digitally traceable framework.

---

## 📂 Repository Architecture

The project codebase is modularized into four operational core phases, guiding the process from initial design to final structure-property evaluation:

### Module 1: Hydrogel Preparation and Automation (Opentrons)
* **`1_hydrogel_preparation_and_opentrons`**: Focuses on data-driven Design of Experiments (DoE) using Latin Hypercube Sampling (LHS) to explore the multivariable space of 32 distinct hydrogel compositions. It contains Opentrons Flex robotic liquid-handling scripts that translate digital formulation tables into automated dispensing volumes for multiwell plates.
  * `LHS_HEMA_PEGDA_LAP_32 formulas.ipynb`: Notebook executing the Latin Hypercube Sampling layout.
  * `lhs_design_space.pdf`: Visual distribution maps of the generated multivariable design space.
  * `HEMA_PEGDA_LAP_WATER_Opntrons protocol 200.py` & `500.py`: Scripted liquid handling protocols tailored for regional volume executions.

### Module 2: Mechanical Indentation Analysis
* **`2_mechanical_indentation_analysis`**: Implements the processing workflows to assess the mechanical response of the synthesized hydrogel networks via indentation-derived Young’s Modulus (MPa).
  * `asmi_indentation_protocol.py`: Script driving automation and load configuration for the physical instrument.
  * `indentation_based Young modulus.ipynb`: Data curation notebook converting raw force-displacement data into standardized elastic modulus values.

### Module 3: Contact Angle Measurement
* **`3_contact_angle_measurement`**: Contains the vision and hardware automation stack for static water contact-angle analysis to characterize apparent surface wettability on oven-dried hydrogels.
  * `Automated_Contact_Angle measurement.ipynb`: Core analytical framework driving droplet segmentation, adaptive baseline selection, and local tangent fitting.
  * `Contact Angle Analysis.ipynb`: Computer-vision processing loop utilizing RMSE-based quality control to filter and approve valid profiles.
  * `Camera_Arduino Protocol.ipynb` & `Dispensing Water Protocol_through HTTP.py`: Embedded routines managing motorized sample positioning, image acquisition, and robotic droplet deposition.

### Module 4: Relationship Between Properties
* **`4_relationship_between_properties`**: Consolidates screening matrix outputs at the formulation level (averaging experimental replicates) to uncover structural dependencies and optimize material performance.
  * `Relationship between two properties.ipynb`: Evaluates the direct relationships between chemical precursors (HEMA, PEGDA, LAP, Water) and characterization endpoints. It implements a **multi-objective Pareto analysis** to map performance trade-offs, successfully identifying the optimal, non-dominated formulations within the design space that simultaneously maximize mechanical stiffness (Young's modulus) and minimize surface contact angle.
---

## 🛠️ System Requirements
To execute the scripts and data processing loops within this pipeline, you require Python 3.8+ and the following libraries:
```bash
pip install numpy pandas matplotlib seaborn opencv-python ultralytics scikit-learn
