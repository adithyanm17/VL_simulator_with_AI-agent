import re

class VCDParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.signals = {} # id -> {'name': name, 'size': size, 'values': [(time, val), ...]}
        self.times = []
        self.max_time = 0

    def parse(self):
        with open(self.filepath, 'r') as f:
            lines = f.readlines()

        current_time = 0
        header_done = False
        current_scope = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if not header_done:
                if line.startswith('$scope'):
                    parts = line.split()
                    if len(parts) >= 3:
                        current_scope.append(parts[2])
                elif line.startswith('$upscope'):
                    if current_scope:
                        current_scope.pop()
                elif line.startswith('$var'):
                    parts = line.split()
                    var_type = parts[1]
                    size = int(parts[2])
                    var_id = parts[3]
                    name = parts[4]
                    self.signals[var_id] = {'name': name, 'size': size, 'values': [], 'path': list(current_scope)}
                elif line.startswith('$enddefinitions'):
                    header_done = True
            else:
                if line.startswith('#'):
                    current_time = int(line[1:])
                    if current_time not in self.times:
                        self.times.append(current_time)
                    self.max_time = max(self.max_time, current_time)
                elif line.startswith('b') or line.startswith('b') or line.startswith('r') or line.startswith('B'):
                    # Vector value change: b100 id
                    match = re.match(r'b([01xXzZ]+)\s+(\S+)', line)
                    if match:
                        val = match.group(1)
                        var_id = match.group(2)
                        if var_id in self.signals:
                            self.signals[var_id]['values'].append((current_time, val))
                elif line[0] in '01xXzZ':
                    # Scalar value change: 1id
                    val = line[0]
                    var_id = line[1:]
                    if var_id in self.signals:
                        self.signals[var_id]['values'].append((current_time, val))
                        
        return self.signals, self.max_time
