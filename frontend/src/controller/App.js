import "./css/app.css";
import React, { useEffect, useState, useRef } from "react";
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

/**
 * Represents a measurement program config.
 * - name: name of the measurement program (e.g. "idvg", "idvd", etc.)
 * - config: config object acts as json dict of parameters for the
 *      measurement program
 */
class MeasurementProgram {
    constructor(name, config) {
        this.name = name;
        this.config = config;
    }
}

/**
 * Represents a auto probing sweep across device locations.
 * - name: name of sweep type (e.g. "single", "array", etc.)
 * - config: config object acts as json dict of parameters for the
 *      sweep type
 */
class Sweep {
    constructor(name, config) {
        this.name = name;
        this.config = config;
    }
}


const App = ({
    axios, // axios instance
}) => {
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

    // measurement program settings
    const [measurementProgramTypes, setMeasurementProgramTypes] = useState([]); // dropdown list of all measurement programs names
    const [measurementPrograms, setMeasurementPrograms] = useState([            // list of user selected measurement programs
        new MeasurementProgram("", ""), // default empty measurement program
    ]);

    // sweep settings
    const [sweepTypes, setSweepTypes] = useState([]);
    const [sweep, setSweep] = useState(new Sweep("", "")); // sweep config object
    const [sweepSaveData, setSweepSaveData] = useState(true);
    const [sweepSaveImage, setSweepSaveImage] = useState(true);
    
    // run dialog open
    const [runConfirmDialog, setRunConfirmDialog] = useState(false);
    
    // measurement status
    const [measurementRunning, setMeasurementRunning] = useState(false);

    // REFS
    const refMeasurementPrograms = useRef(measurementPrograms); // avoids stale closure when async setting measurement programs

    // Function to add a new program to end of programs list
    const addMeasurementProgram = () => {
        const newPrograms = [...measurementPrograms];
        newPrograms.push(new MeasurementProgram("", ""));
        refMeasurementPrograms.current = newPrograms;
        setMeasurementPrograms(newPrograms);
    };

    // Function to remove a program from the programs list
    const removeMeasurementProgram = (index) => {
        const newPrograms = [...measurementPrograms];
        newPrograms.splice(index, 1);
        refMeasurementPrograms.current = newPrograms;
        setMeasurementPrograms(newPrograms);
    };

    // Set measurement config value at index in user programs list
    const setMeasurementProgramConfigAtIndex = (index, newConfig) => {
        const newPrograms = [...measurementPrograms];
        const oldProgramName = newPrograms[index].name;
        newPrograms[index] = new MeasurementProgram(
            oldProgramName, // keep same name
            newConfig,      // use new config
        );
        refMeasurementPrograms.current = newPrograms;
        setMeasurementPrograms(newPrograms);
    };

    // Set sweep config value but keep same name/type
    const setSweepConfig = (newConfig) => {
        setSweep(new Sweep(sweep.name, newConfig));
    };

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
        // unpack measurement programs into separate array of program names and configs
        const programs = [];
        const programConfigs = [];
        for (const program of measurementPrograms) {
            programs.push(program.name);
            programConfigs.push(program.config);
        }

        // push change to server
        axios.put("api/controller", {
            msg: "run_measurement",
            data: { // snake case to follow python internal convention
                user: measurementUser,
                initial_die_x: parseInt(currentDieX),
                initial_die_y: parseInt(currentDieY),
                die_dx: parseFloat(dieSizeX),
                die_dy: parseFloat(dieSizeY),
                initial_device_row: parseInt(deviceRow),
                initial_device_col: parseInt(deviceCol),
                device_dx: parseFloat(deviceX),
                device_dy: parseFloat(deviceY),
                data_folder: dataFolder,
                programs: programs,
                program_configs: programConfigs,
                sweep: sweep.name,
                sweep_config: sweep.config,
                sweep_save_data: sweepSaveData,
                sweep_save_image: sweepSaveImage,
            },
        });

        setMeasurementRunning(true);
        setRunConfirmDialog(false);
    };

    const cancelMeasurement = () => {
        axios.put("api/controller", {
            msg: "cancel_measurement",
            data: {},
        });
    };

    useEffect(() => {
        console.log("<App> Rendered");

        axios.get("api/controller").then(response => {
            setGpibB1500(response.data.gpib_b1500);
            setGpibCascade(response.data.gpib_cascade);
            setMeasurementUserList(response.data.users);
            setMeasurementProgramTypes(response.data.programs);
            setSweepTypes(response.data.sweeps);
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
        responseHandlers.set("measurement_program_config", ({name, index, config}) => {
            const newPrograms = [...refMeasurementPrograms.current];
            newPrograms[index] = new MeasurementProgram(name, config);
            refMeasurementPrograms.current = newPrograms;
            setMeasurementPrograms(newPrograms);
        });
        responseHandlers.set("measurement_sweep_config", ({name, config}) => {
            setSweep(new Sweep(name, config));
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
                        addMeasurementProgram={addMeasurementProgram}
                        removeMeasurementProgram={removeMeasurementProgram}
                        measurementProgramTypes={measurementProgramTypes}
                        measurementPrograms={measurementPrograms}
                        setMeasurementProgramConfigAtIndex={setMeasurementProgramConfigAtIndex}
                        sweepTypes={sweepTypes}
                        sweep={sweep}
                        setSweepConfig={setSweepConfig}
                        sweepSaveData={sweepSaveData}
                        setSweepSaveDataLocal={setSweepSaveData}
                        sweepSaveImage={sweepSaveImage}
                        setSweepSaveImageLocal={setSweepSaveImage}
                        measurementRunning={measurementRunning}
                        handleRunMeasurement={tryRunMeasurement}
                        handleCancelMeasurement={cancelMeasurement}
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
                measurementPrograms={measurementPrograms}
                sweep={sweep}
                sweepSaveData={sweepSaveData}
                sweepSaveImage={sweepSaveImage}
            />
        </Container>
    );
}

export default App;