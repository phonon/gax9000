import "./css/app.css";
import React, { useEffect, useState } from "react";
import {
    Box,
    Button, 
    Container,
    Divider,
    FormControl,
    Grid,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    TextField,
} from "@mui/material";
import {
    DialogRunMeasurement,
    InstrumentConnection,
    MeasurementControls,
    WaferControls,
} from "./components.js";

// GPIB addresses are in range [0, 31]
const GPIB_ADDRESS_RANGE = Array.from(Array(31).keys());

const DEFAULT_MEASUREMENT_CONFIG = `{
  "probe_gate": 8,
  "probe_source": 1,
  "probe_drain": 3,
  "probe_sub": 9,
  "v_gs": {
      "start": -1.2,
      "stop": 1.2,
      "step": 0.1
  },
  "v_ds": [-0.05, -0.4, -1.2]
}`;

function App({
    axios, // axios instance
}) {
    const [gpibB1500, setGpibB1500] = useState(16);
    const [gpibCascade, setGpibCascade] = useState(22);
    const [instrB1500Identification, setInstrB1500Identification] = useState(" ");
    const [instrCascadeIdentification, setInstrCascadeIdentification] = useState(" ");

    // users
    const [measurementUserList, setMeasurementUserList] = useState([]);
    const [measurementUser, setMeasurementUser] = useState("");

    // user settings
    const [dieSizeX, setDieSizeX] = useState(0);
    const [dieSizeY, setDieSizeY] = useState(0);
    const [dieOffsetX, setDieOffsetX] = useState(0);
    const [dieOffsetY, setDieOffsetY] = useState(0);
    const [currentDieX, setCurrentDieX] = useState(0);
    const [currentDieY, setCurrentDieY] = useState(0);
    const [deviceX, setDeviceX] = useState(0);
    const [deviceY, setDeviceY] = useState(0);
    const [deviceRow, setDeviceRow] = useState(0);
    const [deviceCol, setDeviceCol] = useState(0);
    const [dataFolder, setDataFolder] = useState("");

    // program settings
    const [measurementProgramList, setMeasurementProgramList] = useState([]);
    const [measurementProgram, setMeasurementProgram] = useState("");
    const [measurementConfig, setMeasurementConfig] = useState(DEFAULT_MEASUREMENT_CONFIG);

    // sweep settings
    const [sweepList, setSweepList] = useState([]);
    const [sweep, setSweep] = useState("");
    const [sweepConfig, setSweepConfig] = useState("{}");
    const [sweepSaveData, setSweepSaveData] = useState(true);
    
    // run dialog open
    const [runConfirmDialog, setRunConfirmDialog] = useState(false);
    
    // measurement status
    const [measurementRunning, setMeasurementRunning] = useState(false);

    // Function to try and run a measurement.
    // This performs basic checks (e.g. user valid) 
    // and opens a confirmation dialog.
    const tryRunMeasurement = () => {
        if ( measurementUser === "" || (sweepSaveData && dataFolder === "") ) {
            console.error("Missing user or data folder");
            return;
        }
        setRunConfirmDialog(true)
    };
    
    // function to run measurement
    const runMeasurement = () => {
        // push change to server
        axios.put("api/controller", {
            msg: "run_measurement",
            data: { // snake case to follow python internal convention
                user: measurementUser,
                current_die_x: currentDieX,
                current_die_y: currentDieY,
                device_x: deviceX,
                device_y: deviceY,
                device_row: deviceRow,
                device_col: deviceCol,
                data_folder: dataFolder,
                program: measurementProgram,
                program_config: measurementConfig,
                sweep: sweep,
                sweep_config: sweepConfig,
                sweep_save_data: sweepSaveData,
            },
        });

        setMeasurementRunning(true);
        setRunConfirmDialog(false);
    };

    useEffect(() => {
        console.log("<App> Rendered");

        axios.get("api/controller").then(response => {
            setGpibB1500(response.data.gpib_b1500);
            setGpibCascade(response.data.gpib_cascade);
            setMeasurementUserList(response.data.users);
            setMeasurementProgramList(response.data.programs);
            setSweepList(response.data.sweeps);
        }).catch(error => {
            console.log(error)
        });

        // backend api event response handlers
        const responseHandlers = new Map();
        responseHandlers.set("connect_b1500_idn", ({idn}) => {
            setInstrB1500Identification(idn);
        });
        responseHandlers.set("disconnect_b1500", ({}) => {
            setInstrB1500Identification(" ");
        });
        responseHandlers.set("connect_cascade_idn", ({idn}) => {
            setInstrCascadeIdentification(idn);
        });
        responseHandlers.set("disconnect_cascade", ({}) => {
            setInstrCascadeIdentification(" ");
        });
        responseHandlers.set("set_user_settings", ({settings}) => {
            setDieSizeX(settings.die_size_x);
            setDieSizeY(settings.die_size_y);
            setDieOffsetX(settings.die_offset_x);
            setDieOffsetY(settings.die_offset_y);
            setCurrentDieX(settings.current_die_x);
            setCurrentDieY(settings.current_die_y);
            setDeviceX(settings.device_x);
            setDeviceY(settings.device_y);
            setDeviceRow(settings.device_row);
            setDeviceCol(settings.device_col);
            setDataFolder(settings.data_folder);
        });
        responseHandlers.set("measurement_error", ({error}) => {
            console.error("Measurement failed error", error);
            setMeasurementRunning(false);
        });
        responseHandlers.set("measurement_finish", ({status}) => {
            console.log("Measurement finished:", status);
            setMeasurementRunning(false);
        });
        
        // event channel for backend SSE events
        const eventSrc = new EventSource(axios.defaults.baseURL + "/event/controller");
        eventSrc.onmessage = (e) => {
            try {
                const response = JSON.parse(e.data);
                console.log("RESPONSE", response);
                if ( responseHandlers.has(response.msg) ) {
                    responseHandlers.get(response.msg)(response.data);
                } else {
                    console.error("Invalid response msg:", response)
                }
            } catch ( error ) {
                console.error(error);
            }
        };

        eventSrc.onerror = (e) => {
            console.error(e);
            eventSrc.close();
        };

        // clean up event channel
        return () => {
            eventSrc.close();
        };
    }, []);


    return (
        <Container maxWidth="md">
            <Grid
                container
                id="controller"
                spacing={2}
                direction="column"
                justifyContent="center"
                alignItems="center"
            >
                <Grid item sx={{width: "100%"}}>
                    <Box id="measurement-profile" sx={{width: "100%", paddingTop: "20px"}} >
                        <Grid
                            container
                            spacing={4}
                            direction="row"
                        >
                            <Grid item xs={6}>
                                <InstrumentConnection
                                    axios={axios}
                                    label="B1500 Parameter Analyzer"
                                    address={gpibB1500}
                                    setAddressLocal={setGpibB1500}
                                    identification={instrB1500Identification}
                                    addressRange={GPIB_ADDRESS_RANGE}
                                    apiConnectMsg={"connect_b1500"}
                                    apiDisconnectMsg={"disconnect_b1500"}
                                    apiSetAddressMsg={"set_b1500_gpib_address"}
                                />
                            </Grid>

                            <Grid item xs={6}>
                                <InstrumentConnection
                                    axios={axios}
                                    label="Cascade Probe Station"
                                    address={gpibCascade}
                                    setAddressLocal={setGpibCascade}
                                    identification={instrCascadeIdentification}
                                    addressRange={GPIB_ADDRESS_RANGE}
                                    apiConnectMsg={"connect_cascade"}
                                    apiDisconnectMsg={"disconnect_cascade"}
                                    apiSetAddressMsg={"set_cascade_gpib_address"}
                                />
                            </Grid>
                        </Grid>
                    </Box>
                </Grid>

                <Grid item sx={{width: "100%"}}>
                    <Divider/>
                </Grid>

                <Grid item sx={{width: "100%"}}>
                    <WaferControls
                        axios={axios}
                        user={measurementUser}
                        dieSizeX={dieSizeX}
                        setDieSizeXLocal={setDieSizeX}
                        dieSizeY={dieSizeY}
                        setDieSizeYLocal={setDieSizeY}
                        dieOffsetX={dieOffsetX}
                        setDieOffsetXLocal={setDieOffsetX}
                        dieOffsetY={dieOffsetY}
                        setDieOffsetYLocal={setDieOffsetY}
                        currentDieX={currentDieX}
                        setCurrentDieXLocal={setCurrentDieX}
                        currentDieY={currentDieY}
                        setCurrentDieYLocal={setCurrentDieY}
                        deviceX={deviceX}
                        setDeviceXLocal={setDeviceX}
                        deviceY={deviceY}
                        setDeviceYLocal={setDeviceY}
                        deviceRow={deviceRow}
                        setDeviceRowLocal={setDeviceRow}
                        deviceCol={deviceCol}
                        setDeviceColLocal={setDeviceCol}
                    />
                </Grid>

                <Grid item sx={{width: "100%"}}>
                    <Divider/>
                </Grid>

                <Grid item sx={{width: "100%"}}>
                    <MeasurementControls
                        axios={axios}
                        userList={measurementUserList}
                        user={measurementUser}
                        setUserLocal={setMeasurementUser}
                        dataFolder={dataFolder}
                        setDataFolderLocal={setDataFolder}
                        programList={measurementProgramList}
                        program={measurementProgram}
                        setProgramLocal={setMeasurementProgram}
                        programConfig={measurementConfig}
                        setProgramConfig={setMeasurementConfig}
                        sweepList={sweepList}
                        sweep={sweep}
                        setSweepLocal={setSweep}
                        sweepConfig={sweepConfig}
                        setSweepConfigLocal={setSweepConfig}
                        sweepSaveData={sweepSaveData}
                        setSweepSaveDataLocal={setSweepSaveData}
                        measurementRunning={measurementRunning}
                        handleRunMeasurement={tryRunMeasurement}
                    />
                </Grid>
            </Grid>

            {/* Dialog box to confirm running the measurement */}
            <DialogRunMeasurement
                open={runConfirmDialog}
                handleClose={() => setRunConfirmDialog(false)}
                runMeasurement={runMeasurement}
                currentDieX={currentDieX}
                currentDieY={currentDieY}
                deviceX={deviceX}
                deviceY={deviceY}
                deviceRow={deviceRow}
                deviceCol={deviceCol}
                dataFolder={dataFolder}
                program={measurementProgram}
                programConfig={measurementConfig}
                sweep={sweep}
                sweepConfig={sweepConfig}
                sweepSaveData={sweepSaveData}
            />
        </Container>
    );
}

export default App;