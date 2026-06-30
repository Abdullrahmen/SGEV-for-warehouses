import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { useWebSocket } from './WebSocketContext'

const RobotContext = createContext()

export function RobotContextProvider({ children }) {
  const [robots, setRobots] = useState({})
  const [selectedRobot, setSelectedRobot] = useState(null)
  const robotPositions = useRef({})
  const { subscribe } = useWebSocket()

  useEffect(() => {
    const unsubPose = subscribe('robot.pose', (data) => {
      const id = data.robot_id
      const prev = robotPositions.current[id]
      const now = Date.now()
      robotPositions.current[id] = {
        prevX: prev?.targetX ?? data.x,
        prevY: prev?.targetY ?? data.y,
        prevYaw: prev?.targetYaw ?? data.yaw,
        targetX: data.x,
        targetY: data.y,
        targetYaw: data.yaw,
        timestamp: now,
      }
    })

    const unsubStatus = subscribe('robot.status', (data) => {
      setRobots((prev) => ({
        ...prev,
        [data.robot_id]: {
          ...prev[data.robot_id],
          system_status: data.system_status,
        },
      }))
    })

    const unsubMode = subscribe('robot.mode', (data) => {
      setRobots((prev) => ({
        ...prev,
        [data.robot_id]: {
          ...prev[data.robot_id],
          operational_mode: data.operational_mode,
          controlled_by: data.controlled_by,
        },
      }))
    })

    const unsubMission = subscribe('robot.mission', (data) => {
      const status = data.status === 'COMPLETED' ? 'completed' : 'failed'
    })

    return () => {
      unsubPose()
      unsubStatus()
      unsubMode()
      unsubMission()
    }
  }, [subscribe])

  const updateRobot = useCallback((robotData) => {
    setRobots((prev) => ({
      ...prev,
      [robotData.robot_id]: {
        ...prev[robotData.robot_id],
        ...robotData,
      },
    }))
  }, [])

  return (
    <RobotContext.Provider value={{ robots, robotPositions, selectedRobot, setSelectedRobot, updateRobot }}>
      {children}
    </RobotContext.Provider>
  )
}

export const useRobotContext = () => useContext(RobotContext)
