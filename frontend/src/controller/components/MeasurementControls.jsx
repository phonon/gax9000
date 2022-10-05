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
import { useEffect } from "react";


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

const handleChangeMeasurementProgram = (axios, user, index, oldProgram, oldProgramConfig, newProgram, setProgramAtIndex) => {
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
            index: index,
        },
    });

    // set program locally in app
    setProgramAtIndex(index, newProgram);
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
 * CodeMirror code editor with synchronized local value. This is to
 * deal with issue of cursor jumping to beginning when typing too fast
 * due to element being re-rendered.
 * 
 * But because code mirror updated locally, we need another variable
 * to synchronize when program or config changes. This is the `config`
 * value which can be the selection title or list index. When this 
 * changes, then push external value into local value.
 */
const SynchronizedCodeMirrorEditor = ({
    config,   // selected program or config, for detecting when to update local value
    value,    // external value
    onChange,
}) => {
    const [localVal, setLocalVal] = React.useState(value);
    
    useEffect(() => {
        setLocalVal(value);
    }, [config]);

    return <CodeMirror
        value={localVal}
        theme="light"
        height="200px"
        minHeight="160px"
        extensions={[
            codeMirrorJsonExtension(),
        ]}
        onChange={(newValue, viewUpdate) => {
            // make update synchronous, to avoid cursor jumping when the value
            // doesn't change asynchronously 
            setLocalVal(newValue);
            // make the real update afterwards
            onChange(newValue);
        }}
    />
}

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
    addMeasurementProgram,
    removeMeasurementProgram,
    programList,
    programs,
    setProgramAtIndex,
    programConfigsNames,
    programConfigs,
    setProgramConfigAtIndex,
    sweepList,
    sweep,
    setSweepLocal,
    sweepConfigName,
    sweepConfig,
    setSweepConfigLocal,
    sweepSaveData,
    setSweepSaveDataLocal,
    sweepSaveImage,
    setSweepSaveImageLocal,
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

    let programMenuItems = programList.map((x) =>
        <MenuItem key={x} value={x}>{x}</MenuItem>
    );

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
                        {/* Measurement program configs */}
                        <Grid item xs={6}>
                            {/* create program selection + editor for each index */}
                            {programs.map((program, index) =>
                                <Box key={index} sx={{padding: "0px 0px 16px 0px"}}>
                                    <Grid
                                        container
                                        spacing={0}
                                        direction="row"
                                    >
                                        <Grid item xs={10.8}>
                                            <FormControl fullWidth>
                                                <InputLabel id="measurement-program-select-label">Program</InputLabel>
                                                <Select
                                                    id="measurement-program-select"
                                                    labelId="measurement-program-select-label"
                                                    value={program}
                                                    label="Program"
                                                    size="small"
                                                    onChange={(e) => handleChangeMeasurementProgram(axios, user, index, program, programConfigs[index], e.target.value, setProgramAtIndex)}
                                                >
                                                    {programMenuItems}
                                                </Select>
                                            </FormControl>
                                        </Grid>

                                        {/* Button add new program */}
                                        <Grid
                                            item xs={1.2}
                                        >
                                            <Button
                                                fullWidth
                                                variant="outlined"
                                                color="error"
                                                size="large"
                                                sx={{width: "100%", minWidth: "0px"}}
                                                onClick={() => removeMeasurementProgram(index)}
                                            >
                                                ✖
                                            </Button>
                                        </Grid>
                                    </Grid>
                                    {/* <CodeMirror
                                        value={programConfigs[index]}
                                        theme="light"
                                        height="200px"
                                        minHeight="200px"
                                        extensions={[
                                            codeMirrorJsonExtension(),
                                        ]}
                                        onChange={(value, viewUpdate) => {
                                            setProgramConfigAtIndex(index, value);
                                        }}
                                    /> */}
                                    <SynchronizedCodeMirrorEditor
                                        config={programConfigsNames[index]}
                                        value={programConfigs[index]}
                                        onChange={(val) => setProgramConfigAtIndex(index, val)}
                                    />
                                </Box>
                            )}
                            {/* Button add new program */}
                            <Button
                                fullWidth
                                variant="outlined"
                                onClick={addMeasurementProgram}
                            >
                                Add program
                            </Button>
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
                                {/* <CodeMirror
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
                                /> */}
                                <SynchronizedCodeMirrorEditor
                                    config={sweepConfigName}
                                    value={sweepConfig}
                                    onChange={(val) => setSweepConfigLocal(val)}
                                />
                                
                                {/* Start measurement button and save data configs */}
                                <FormGroup sx={{flexDirection: "row"}}>
                                    <FormControlLabel control={<Checkbox checked={sweepSaveData} onChange={(e) => setSweepSaveDataLocal(e.target.checked)}/>} label="Save Data" />
                                    <FormControlLabel control={<Checkbox checked={sweepSaveImage} onChange={(e) => setSweepSaveImageLocal(e.target.checked)}/>} label="Save Image" />
                                </FormGroup>

                                <Grid item>
                                    <Grid
                                        container
                                        spacing={1}
                                        direction="row"
                                        >                                        
                                        <Grid item xs={10}>
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
                            </Box>
                        </Grid>

                    </Grid>
                </Box>
            </Grid>
        </Grid>
    );
}
