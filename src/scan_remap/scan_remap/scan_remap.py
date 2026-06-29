import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
import math


class scan_remap(Node):
    """
    Subscribes to /scan_raw (RPLiDAR driver output),
    zeros out angles that see the car chassis,
    and republishes on /scan for all downstream packages.
    """

    def __init__(self):
        super().__init__('scan_remap')

        # ------------------------------------------------------------------ #
        #  Declare parameters — override in launch file or YAML              #
        # ------------------------------------------------------------------ #
        self.declare_parameter('input_topic',  '/scan_raw')
        self.declare_parameter('output_topic', '/scan')

        # List of blocked angle ranges as a flat list of pairs:
        #   [min1, max1, min2, max2, ...]  — all values in DEGREES
        # Default: block 150°–210° (rear chassis, centered on 180°)
        self.declare_parameter('blocked_angles_deg', [0,10,158,232,245,256,285,292,308,322,350,360])

        # Value to replace blocked ranges with:
        #   float('inf')  — range is "too far" (safe for Nav2 / costmaps)
        #   float('nan')  — range is "invalid" (filtered out completely)
        self.declare_parameter('replace_with_inf', True)

        self._read_params()

        self.sub = self.create_subscription(
            LaserScan,
            self._input_topic,
            self._scan_callback,
            10
        )
        self.pub = self.create_publisher(
            LaserScan,
            self._output_topic,
            10
        )

        self.get_logger().info(
            f'Chassis filter active: {self._input_topic} → {self._output_topic}'
        )
        self.get_logger().info(
            f'Blocked ranges (deg): {self._blocked_ranges}'
        )

    # ---------------------------------------------------------------------- #
    #  Parameter loading                                                      #
    # ---------------------------------------------------------------------- #
    def _read_params(self):
        self._input_topic  = self.get_parameter('input_topic').value
        self._output_topic = self.get_parameter('output_topic').value
        self._replace_inf  = self.get_parameter('replace_with_inf').value

        flat = self.get_parameter('blocked_angles_deg').value
        if len(flat) % 2 != 0:
            self.get_logger().error(
                'blocked_angles_deg must have an even number of values (pairs). '
                'Ignoring last value.'
            )
            flat = flat[:-1]

        # Build list of (min_deg, max_deg) tuples
        self._blocked_ranges = [
            (float(flat[i]), float(flat[i + 1]))
            for i in range(0, len(flat), 2)
        ]

    # ---------------------------------------------------------------------- #
    #  Scan callback                                                          #
    # ---------------------------------------------------------------------- #
    def _scan_callback(self, msg: LaserScan):
        replacement = float('inf') if self._replace_inf else float('nan')

        ranges = list(msg.ranges)

        for i in range(len(ranges)):
            angle_rad = msg.angle_min + i * msg.angle_increment
            # Normalize to 0–360°
            angle_deg = math.degrees(angle_rad) % 360.0

            for (lo, hi) in self._blocked_ranges:
                if lo <= angle_deg <= hi:
                    ranges[i] = replacement
                    break

        # Publish — reuse the original message header and metadata
        out = LaserScan()
        out.header         = msg.header
        out.angle_min      = msg.angle_min
        out.angle_max      = msg.angle_max
        out.angle_increment = msg.angle_increment
        out.time_increment = msg.time_increment
        out.scan_time      = msg.scan_time
        out.range_min      = msg.range_min
        out.range_max      = msg.range_max
        out.ranges         = ranges
        out.intensities    = msg.intensities

        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = scan_remap()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
