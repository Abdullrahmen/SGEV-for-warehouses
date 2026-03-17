from setuptools import setup

package_name = 'esp32_uart_comm'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    py_modules=['ros2_uart_node'],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='user@example.com',
    description='ROS2 node for UART communication with ESP32',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'ros2_uart_node = ros2_uart_node:main',
        ],
    },
)
