cmake_minimum_required(VERSION 3.8)
project(robot_simulation)

find_package(ament_cmake REQUIRED)

ament_package()

install(DIRECTORY worlds launch config scripts
  DESTINATION share/${PROJECT_NAME}
)
