# Initial Research on Existing Procedural Building Generators
I'd like to make a project which can use open-source code to generate large-commercial and industrial building floor plans. The goal is to be able to create a 3D render-able single 3D floor-plan for use in a building controller-and-sensor wireless network simulator. Based on some parameters related to densitity of controllers, controller-to-sensor ratio, wall-material types, etc, it will generate a possible floor layout with the sensors and controllers on the walls. It will then be able to trace the shortest path between each and every sensor/controller and create an object representing said path, recording it's distance and a list of the walls passed through so their quantity and respective materials are usable for a signal-strength path-loss model I will provide based on research. I'll then use this as a training environment for the wireless sensor networking algorithms on each device by simulating policies over a set of building scenarios and evaluating the scoring. 

## Building Generator Resources
### ArchiGAN a Generative Stack for Apartment Building Design
https://developer.nvidia.com/blog/archigan-generative-stack-apartment-building-design/
https://github.com/archiGAN/SmartCity
https://stanislaschaillou.com/thesis/GAN/unit_program/

### Procedural-Building-Generator
Made for making floorplans in Blender. Perhaps could be useful. Could the source-code be adapted for my use-case?
https://github.com/wojtryb/Procedural-Building-Generator
