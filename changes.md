# Important changes to the current state of the project
## Door placement
### Simplistic placement
The door placement is too simplistic in that the doors are placed in the midpoint of the corresponding wall. In reality that just isn't the case. Switch to a random location on the wall at least 1 door length from the edge. If that isn't possible, put it in the center.
### Dramatic shape in visualizer
The doors are represented as an entire brown circle which is confusing. It makes it look like a sensor node. Favor a partially transparent quarter-circle as is typically drawn in architectural drawings to distinguish it from networking devices.

## Sensor placement
### Simplistic placement
The sensors are placed in the center of the room every time. They should have a random location on the wall between the two end-points. 
### Choose a side of the wall.
From the visualizer it is unclear which side of the wall the sensor is on. I haven't reviewed the code so I'm not even certain if it has a truly defined side of the wall; it most definitely SHOULD have a specific side. This specific side will dictate how many walls the different link paths must cross. That wall could represent 1 or 0 crossings depending on the direction. Make sure a side is chosen so that every room has at least 1 sensor inside it and when it is drawn, drawn the circle tangent to the wall rather than colinear with the centroid. 

Care must be taken to ensure it never ends up on the exterior of the building.

### Multiple sensors in a room
I would like to make sure that there is a yaml file which shows the rules for sensor quantitiy in spaces. There should be a minimum count per room and a minimum count per sqft which is enforced by evaluating whether a room needs 1 or N sensors and then distributes them in the space on the walls.

## Controller placement
Just as with the sensors I would like the controller minimum sq-ft density to be represented in the aforementioned yaml file. They do not have a minimum count per room but instead have a minimum count per area. The main controllers and satellite controllers should have independent values for this.

## Zone proportions
Many seeds lead to zones with odd proportions. The rectangular zones are drastically longer than wide and vice versa creating groups of spaces that look more like corridors than rooms. The zones should not generally have a side-to-side ratio larger than 2x.