import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Box, Grid, Card, CardContent, Typography, Select, MenuItem, FormControl,
  InputLabel, Button, CircularProgress, Alert, Chip,
} from '@mui/material'
import MapCanvas from '../components/MapCanvas'
import { useRobotContext } from '../contexts/RobotContext'
import { useWebSocket } from '../contexts/WebSocketContext'
import api from '../api'

const KEY_MAP = {
  KeyW: 'W', KeyA: 'A', KeyS: 'S', KeyD: 'D',
}

export default function ManualControl() {
  const [robotList, setRobotList] = useState([])
  const [activeMap, setActiveMap] = useState(null)
  const [products, setProducts] = useState([])
  const [targetPosition, setTargetPosition] = useState(null)
  const [loading, setLoading] = useState(true)
  const [pressedKey, setPressedKey] = useState(null)
  const activeKeyRef = useRef(null)
  const intervalRef = useRef(null)
  const { robots, robotPositions, selectedRobot, setSelectedRobot } = useRobotContext()
  const { sendMessage } = useWebSocket()

  const fetchData = async () => {
    try {
      const [robotsRes, mapRes] = await Promise.all([
        api.get('/robots/'),
        api.get('/maps/active/').catch(() => null),
      ])
      setRobotList(robotsRes.data.results || robotsRes.data)
      if (mapRes) {
        setActiveMap(mapRes.data)
        const posRes = await api.get(`/product-positions/?map=${mapRes.data.id}`)
        setProducts(posRes.data.results || posRes.data)
      }
    } catch {} finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const currentRobot = selectedRobot ? robots[selectedRobot] : null
  const mergedRobotList = robotList.map((r) => ({ ...r, ...robots[r.robot_id] }))
  const onlineRobots = mergedRobotList.filter((r) => r.system_status === 'ONLINE')
  const isControlling = currentRobot?.controlled_by === localStorage.getItem('username')
  const canDrive = currentRobot?.operational_mode === 'MANUAL' || currentRobot?.operational_mode === 'MAPPING'

  const sendCommand = useCallback((command) => {
    if (!selectedRobot) return
    sendMessage({ type: 'cmd_manual', robot_id: selectedRobot, command })
  }, [selectedRobot, sendMessage])

  const stopMovement = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (activeKeyRef.current) {
      sendCommand('STOP')
      activeKeyRef.current = null
    }
  }, [sendCommand])

  const handleKeyDown = useCallback((e) => {
    const key = KEY_MAP[e.code]
    if (!key || !isControlling || !canDrive) return
    e.preventDefault()
    if (activeKeyRef.current) return
    activeKeyRef.current = key
    setPressedKey(key)
    sendCommand(key)
    intervalRef.current = setInterval(() => sendCommand(key), 100)
  }, [isControlling, canDrive, sendCommand])

  const handleKeyUp = useCallback((e) => {
    const key = KEY_MAP[e.code]
    if (!key) return
    if (activeKeyRef.current === key) {
      setPressedKey(null)
      stopMovement()
    }
  }, [stopMovement])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      stopMovement()
    }
  }, [handleKeyDown, handleKeyUp, stopMovement])

  const takeControl = async () => {
    if (!selectedRobot) return
    try {
      await api.put(`/robots/${selectedRobot}/set_mode/`, { mode: 'MANUAL' })
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to take control')
    }
  }

  const releaseControl = async () => {
    if (!selectedRobot) return
    try {
      await api.put(`/robots/${selectedRobot}/set_mode/`, { mode: 'IDLE' })
      setTargetPosition(null)
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to release control')
    }
  }

  const cancelAutoMove = async () => {
    if (!selectedRobot) return
    try {
      await api.put(`/robots/${selectedRobot}/set_mode/`, { mode: 'MANUAL' })
      setTargetPosition(null)
    } catch {}
  }

  const handleMapClick = async (mx, my) => {
    if (!selectedRobot || !isControlling) return
    try {
      await api.post(`/robots/${selectedRobot}/navigate/`, { x: mx, y: my })
      setTargetPosition({ x: mx, y: my })
    } catch {}
  }

  const handleClickTakeBtn = async () => {
    await takeControl()
    fetchData()
  }

  const handleClickReleaseBtn = async () => {
    await releaseControl()
    fetchData()
  }

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}><CircularProgress /></Box>

  return (
    <Grid container spacing={2} sx={{ height: 'calc(100vh - 100px)' }}>
      <Grid xs={12} md={8} sx={{ height: '100%' }}>
        {activeMap ? (
          <MapCanvas
            mapData={activeMap}
            robotPositions={robotPositions}
            robots={robots}
            products={products}
            showHome
            highlightedRobotId={isControlling ? selectedRobot : null}
            targetPosition={targetPosition}
            onMapClick={isControlling ? handleMapClick : null}
          />
        ) : (
          <Alert severity="info">No active map set</Alert>
        )}
      </Grid>
      <Grid xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Control Panel</Typography>
            <FormControl fullWidth margin="normal" disabled={isControlling}>
              <InputLabel>Robot</InputLabel>
              <Select label="Robot" value={selectedRobot || ''} onChange={(e) => setSelectedRobot(e.target.value)}>
                {onlineRobots.map((r) => (
                  <MenuItem key={r.robot_id} value={r.robot_id}>{r.robot_id} - {r.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            {currentRobot && (
              <Box mt={2}>
                <Typography variant="body2">Status: <Chip size="small" label={currentRobot.system_status} color={currentRobot.system_status === 'ONLINE' ? 'success' : 'error'} /></Typography>
                <Typography variant="body2">Mode: {currentRobot.operational_mode}</Typography>
                <Typography variant="body2">Position: ({currentRobot.pos_x?.toFixed(2)}, {currentRobot.pos_y?.toFixed(2)})</Typography>
                <Typography variant="body2">Yaw: {currentRobot.yaw?.toFixed(2)} rad</Typography>
              </Box>
            )}
            <Box mt={2}>
              {!isControlling ? (
                <Button variant="contained" fullWidth onClick={handleClickTakeBtn} disabled={!selectedRobot}>
                  Take Control
                </Button>
              ) : (
                <>
                  <Button variant="outlined" fullWidth color="error" onClick={handleClickReleaseBtn}>
                    Release Control
                  </Button>
                  {currentRobot?.operational_mode === 'SEMI_MANUAL' && (
                    <Button variant="outlined" fullWidth onClick={cancelAutoMove} sx={{ mt: 1 }}>
                      Cancel Auto-Move
                    </Button>
                  )}
                </>
              )}
            </Box>
            {isControlling && (
              <Box mt={3} textAlign="center">
                <Typography variant="body2" gutterBottom>WASD Controls</Typography>
                <Grid container spacing={1} sx={{ justifyContent: 'center' }}>
                  <Grid xs={12} textAlign="center">
                    <Button variant="contained" disabled={!canDrive} sx={{ width: 60, height: 60, filter: pressedKey === 'W' ? 'brightness(1.3)' : 'none' }}
                      onMouseDown={() => { setPressedKey('W'); sendCommand('W'); intervalRef.current = setInterval(() => sendCommand('W'), 100) }}
                      onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>W</Button>
                  </Grid>
                  <Grid xs={4} textAlign="right">
                    <Button variant="contained" disabled={!canDrive} sx={{ width: 60, height: 60, filter: pressedKey === 'A' ? 'brightness(1.3)' : 'none' }}
                      onMouseDown={() => { setPressedKey('A'); sendCommand('A'); intervalRef.current = setInterval(() => sendCommand('A'), 100) }}
                      onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>A</Button>
                  </Grid>
                  <Grid xs={4} textAlign="center">
                    <Button variant="contained" disabled={!canDrive} sx={{ width: 60, height: 60, filter: pressedKey === 'S' ? 'brightness(1.3)' : 'none' }}
                      onMouseDown={() => { setPressedKey('S'); sendCommand('S'); intervalRef.current = setInterval(() => sendCommand('S'), 100) }}
                      onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>S</Button>
                  </Grid>
                  <Grid xs={4} textAlign="left">
                    <Button variant="contained" disabled={!canDrive} sx={{ width: 60, height: 60, filter: pressedKey === 'D' ? 'brightness(1.3)' : 'none' }}
                      onMouseDown={() => { setPressedKey('D'); sendCommand('D'); intervalRef.current = setInterval(() => sendCommand('D'), 100) }}
                      onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>D</Button>
                  </Grid>
                  <Grid xs={12} textAlign="center">
                    <Button variant="outlined" disabled={!canDrive} sx={{ width: 60, height: 60 }}
                      onMouseDown={() => { sendCommand('STOP'); stopMovement() }}>▼</Button>
                  </Grid>
                </Grid>
              </Box>
            )}
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  )
}
