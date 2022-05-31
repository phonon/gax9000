import {
    Box,
    Button, 
    Checkbox,
    Container,
    Divider,
    FormControl,
    FormControlLabel,
    FormGroup,
    Grid,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    TextField,
} from "@mui/material";
import CodeMirror from  "@uiw/react-codemirror";
import { json as codeMirrorJsonExtension } from "@codemirror/lang-json";


const handleSetUserProfile = (axios, username, setUserLocal) => {
    axios.put("api/controller", {
        msg: "get_user_settings",
        data: {
            user: username,
        },
    });
    setUserLocal(username);
}

/**
 * Wrapper for setting a user profile setting in backend
 * and local value in react app.
 * @param {Axios} axios - axios instance
 * @param {string} user - username of user
 * @param {string} oldValue - old value for checking if value changed
 * @param {string} newValue - new input value in field
 * @param {function} setValueLocal - function to set local value
 */
 const handleSetUserDataFolder = (axios, user, oldValue, newValue, setValueLocal) => {
    // invalid user
    if ( user === "" ) {
        return
    }

    // only update if value actually changed
    if ( oldValue !== newValue ) {
        // push change to server
        axios.put("api/controller", {
            msg: "set_user_setting",
            data: {
                user: user,
                setting: "data_folder",
                value: newValue,
            },
        });

        // set local value to raw value (not parsed)
        // to avoid getting stuck with "NaN"
        setValueLocal(newValue);
    }
};

const handleChangeMeasurementProgram = (axios, user, oldProgram, oldProgramConfig, newProgram, setProgramLocal) => {
    if ( user === "" ) { // skip empty user
        return
    }

    // push current program config to controller
    // this makes sure any outstanding changes are saved
    if ( oldProgram !== "" ) {
        axios.put("api/controller", {
            msg: "set_measurement_program_config",
            data: {
                user: user,
                program: oldProgram,
                config: oldProgramConfig,
            },
        });
    }

    // push new program to controller
    axios.put("api/controller", {
        msg: "get_measurement_program_config",
        data: {
            user: user,
            program: newProgram,
        },
    });

    // set program locally in app
    setProgramLocal(newProgram);
};

const handleChangeMeasurementSweep = (axios, user, oldSweep, oldSweepConfig, newSweep, setSweepLocal) => {
    if ( user === "" ) { // skip empty user
        return
    }

    // push current sweep config to controller
    // this makes sure any outstanding changes are saved
    if ( oldSweep !== "" ) {
        axios.put("api/controller", {
            msg: "set_measurement_sweep_config",
            data: {
                user: user,
                sweep: oldSweep,
                config: oldSweepConfig,
            },
        });
    }

    // request new sweep config to controller
    axios.put("api/controller", {
        msg: "get_measurement_sweep_config",
        data: {
            user: user,
            sweep: newSweep,
        },
    });

    // set program locally in app
    setSweepLocal(newSweep);
};

/**
 * Measurement controls ui
 */
export const MeasurementControls = ({
    axios,
    userList,
    user,
    setUserLocal,
    dataFolder,
    setDataFolderLocal,
    programList,
    program,
    setProgramLocal,
    programConfig,
    setProgramConfigLocal,
    sweepList,
    sweep,
    setSweepLocal,
    sweepConfig,
    setSweepConfigLocal,
    sweepSaveData,
    setSweepSaveDataLocal,
    measurementRunning,
    handleRunMeasurement,
    handleCancelMeasurement,
}) => {

    // required to run measurement
    const missingUserOrDataFolder = user === "" || (sweepSaveData && dataFolder === "");

    // measurement status text
    let measurementStatusText = "Start Measurement";
    if ( measurementRunning ) {
        measurementStatusText = "Measurement Running...";
    } else if ( missingUserOrDataFolder ) {
        measurementStatusText = "Missing User or Data Folder";
    }

    return (
        <Grid
            container
            id="measurement-controller"
            spacing={2}
            direction="column"
            justifyContent="center"
            alignItems="center"
        >
            <Grid item sx={{width: "100%"}}>
                <Box id="measurement-user" sx={{width: "100%"}} >
                    <Grid
                        container
                        spacing={1}
                        direction="row"
                    >
                        <Grid item xs={2}>
                            <FormControl fullWidth size="small">
                                <InputLabel id="measurement-user-select-label" size="small">Profile</InputLabel>
                                <Select
                                    id="measurement-user-select"
                                    labelId="measurement-user-select-label"
                                    value={user}
                                    label="User"
                                    size="small"
                                    onChange={(e) => handleSetUserProfile(axios, e.target.value, setUserLocal)}
                                >
                                    {userList.map((u) =>
                                        <MenuItem key={u} value={u}>{u}</MenuItem>
                                    )}
                                </Select>
                            </FormControl>
                        </Grid>

                        <Grid item xs={8}>
                            <TextField
                                fullWidth
                                id="outlined-basic"
                                label="Data Folder"
                                variant="outlined"
                                size="small"
                                value={dataFolder}
                                onChange={(e) => handleSetUserDataFolder(axios, user, dataFolder, e.target.value, setDataFolderLocal)}
                            />
                        </Grid>
                        
                        <Grid item xs={2}>
                            <input
                                hidden
                                type="file"
                                id="measurement-data-path"
                                webkitdirectory=""
                                directory=""
                                onChange={(e) => console.log("(TODO) CHANGE", e, e.target.files[0].name)}
                            />
                            <label htmlFor="measurement-data-path">
                                <Button
                                    fullWidth
                                    variant="outlined"
                                    component="span"
                                >
                                    Browse
                                </Button>
                            </label> 
                        </Grid>
                    </Grid>
                </Box>
            </Grid>

            {/* Measurement program and sweep config */}
            <Grid item sx={{width: "100%"}}>
                <Box id="measurement-program" sx={{width: "100%"}}>
                    <Grid
                        container
                        spacing={1}
                        direction="row"
                    >
                        {/* Measurement program config */}
                        <Grid item xs={6}>
                            <Box>
                                <FormControl fullWidth>
                                    <InputLabel id="measurement-program-select-label">Program</InputLabel>
                                    <Select
                                        id="measurement-program-select"
                                        labelId="measurement-program-select-label"
                                        value={program}
                                        label="Program"
                                        size="small"
                                        onChange={(e) => handleChangeMeasurementProgram(axios, user, program, programConfig, e.target.value, setProgramLocal)}
                                    >
                                        {programList.map((x) =>
                                            <MenuItem key={x} value={x}>{x}</MenuItem>
                                        )}
                                    </Select>
                                </FormControl>
                                <CodeMirror
                                    value={programConfig}
                                    theme="light"
                                    height="260px"
                                    minHeight="200px"
                                    extensions={[
                                        codeMirrorJsonExtension(),
                                    ]}
                                    onChange={(value, viewUpdate) => {
                                        setProgramConfigLocal(value);
                                    }}
                                />
                            </Box>
                        </Grid>
                        
                        {/* Measurement sweep config */}
                        <Grid item xs={6}>
                            <Box>
                                <FormControl fullWidth>
                                    <InputLabel id="measurement-sweep-select-label">Sweep</InputLabel>
                                    <Select
                                        id="measurement-sweep-select"
                                        labelId="measurement-sweep-select-label"
                                        value={sweep}
                                        label="Sweep"
                                        size="small"
                                        onChange={(e) => handleChangeMeasurementSweep(axios, user, sweep, sweepConfig, e.target.value, setSweepLocal)}
                                    >
                                        {sweepList.map((x) =>
                                            <MenuItem key={x} value={x}>{x}</MenuItem>
                                        )}
                                    </Select>
                                </FormControl>
                                <CodeMirror
                                    value={sweepConfig}
                                    theme="light"
                                    height="200px"
                                    minHeight="160px"
                                    extensions={[
                                        codeMirrorJsonExtension(),
                                    ]}
                                    onChange={(value, viewUpdate) => {
                                        setSweepConfigLocal(value);
                                    }}
                                />
                                
                                <FormGroup>
                                    <FormControlLabel control={<Checkbox checked={sweepSaveData} onChange={(e) => setSweepSaveDataLocal(e.target.checked)}/>} label="Save Data" />
                                </FormGroup>
                            </Box>
                        </Grid>
                    </Grid>
                </Box>
            </Grid>

            {/* Start measurement button and save data configs */}
            <Grid item sx={{width: "100%"}}>
                <Grid
                    container
                    spacing={1}
                    direction="row"
                >
                    <Grid item xs={6}/>
                    
                    <Grid item xs={4}>
                        <Button
                            fullWidth
                            variant={measurementRunning ? "outlined" : "contained"}
                            onClick={handleRunMeasurement}
                            disabled={missingUserOrDataFolder}
                        >
                            {measurementStatusText}
                        </Button>
                    </Grid>
                    <Grid item xs={2}>
                        <Button
                            fullWidth
                            variant="outlined"
                            color="error"
                            onClick={handleCancelMeasurement}
                        >
                            Stop
                        </Button>
                    </Grid>
                </Grid>
                
            </Grid>
        </Grid>
    );
}
