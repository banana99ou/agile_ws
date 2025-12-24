# ROS 2 + workspace
source /opt/ros/humble/setup.bash
source ~/agilex_ws/install/setup.bash

# Use a fixed domain for all robot-related terminals
export ROS_DOMAIN_ID=0

# Use default RMW implementation (FastDDS)
unset RMW_IMPLEMENTATION

# Make sure we’re not in localhost-only discovery mode
unset ROS_LOCALHOST_ONLY
ros2 daemon stop
ros2 daemon start
