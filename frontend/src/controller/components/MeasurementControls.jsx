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
    program,
    setProgramLocal,
    programConfig,
    sweep,
    setSweepLocal,
    sweepConfig,
}) => {
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
            <Grid item sx={{width: "100%"}}>
                <Box id="measurement-program" sx={{width: "100%"}}>
                    <Grid
                        container
                        spacing={1}
                        direction="row"
                    >
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
                                        onChange={(e) => setProgramLocal(e.target.value)}
                                    >
                                        <MenuItem value={"Keysight_IdVgs"}>Keysight_IdVgs</MenuItem>
                                        <MenuItem value={"Keysight_IdVds"}>Keysight_IdVds</MenuItem>
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
                                        console.log('value:', value);
                                    }}
                                />
                            </Box>
                        </Grid>

                        <Grid item xs={6}>
                            <Grid
                                container
                                spacing={1}
                                direction="column"
                            >
                                {/* Measurement sweep config */}
                                <Grid item>
                                    <Box>
                                        <FormControl fullWidth>
                                            <InputLabel id="measurement-sweep-select-label">Sweep</InputLabel>
                                            <Select
                                                id="measurement-sweep-select"
                                                labelId="measurement-sweep-select-label"
                                                value={sweep}
                                                label="Sweep"
                                                size="small"
                                                onChange={(e) => setSweepLocal(e.target.value)}
                                            >
                                                <MenuItem value={"Single"}>Single</MenuItem>
                                                <MenuItem value={"Array"}>Array</MenuItem>
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
                                                console.log('value:', value);
                                            }}
                                        />
                                    </Box>
                                </Grid>

                                {/* Buttons to start measurement */}
                                <Grid item>
                                    <Grid
                                        container
                                        spacing={1}
                                        direction="row"
                                    >
                                        <Grid item xs={9}>
                                            <Button
                                                fullWidth
                                                variant="contained"
                                            >
                                                Start Measurement
                                            </Button>
                                        </Grid>
                                        <Grid item xs={3}>
                                            <Button
                                                fullWidth
                                                variant="outlined"
                                                color="error"
                                            >
                                                Stop
                                            </Button>
                                        </Grid>
                                    </Grid>
                                </Grid>
                            </Grid>
                            
                        </Grid>
                    </Grid>
                </Box>
            </Grid>
        </Grid>
    );
}
