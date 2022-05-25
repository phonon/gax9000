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
 * Measurement controls ui
 */
export const MeasurementControls = ({
    axios,
    userList,
    user,
    setUserLocal,
    program,
    setProgramLocal,
    config,
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
                        <Grid item xs={10}>
                            <TextField
                                fullWidth
                                id="outlined-basic"
                                label="Data Folder"
                                variant="outlined"
                                size="small"
                            />
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
                                    value={config}
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
                </Box>
            </Grid>
        </Grid>
    );
}
