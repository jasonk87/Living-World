
class Crop:
    def __init__(self, crop_type, x, y, growth_stage=0, water_level=100):
        self.crop_type = crop_type
        self.x = x
        self.y = y
        self.growth_stage = growth_stage
        self.water_level = water_level
        self.max_growth_stage = 4  # e.g., 0: seeded, 1: sprouting, 2: growing, 3: mature, 4: withered
        self.map_char = '.' # seeded

    def grow(self):
        if self.growth_stage < self.max_growth_stage -1:
            self.growth_stage += 1
        self.water_level -= 10
        self._update_map_char()

    def update(self, world):
        # Simply grow for now. Later could be affected by weather, etc.
        self.grow()

    def _update_map_char(self):
        if self.growth_stage == 0:
            self.map_char = '.'
        elif self.growth_stage == 1:
            self.map_char = 'v'
        elif self.growth_stage == 2:
            self.map_char = 'Y'
        elif self.growth_stage == 3:
            self.map_char = 'W' # Ready for harvest (Wheat)
        else:
            self.map_char = 'x' # withered


    def to_dict(self):
        return {
            "crop_type": self.crop_type,
            "x": self.x,
            "y": self.y,
            "growth_stage": self.growth_stage,
            "water_level": self.water_level,
            "map_char": self.map_char
        }
