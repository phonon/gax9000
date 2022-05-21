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


/**
 * Measurement controls ui
 */
export const MeasurementControls = (props) => {
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
                <Box id="measurement-profile" sx={{width: "100%"}} >
                    <Grid
                        container
                        spacing={1}
                        direction="row"
                    >
                        <Grid item xs={2}>
                        <FormControl fullWidth size="small">
                            <InputLabel id="measurement-profile-select-label" size="small">Profile</InputLabel>
                            <Select
                                id="measurement-profile-select"
                                labelId="measurement-profile-select-label"
                                value={props.profile}
                                label="Profile"
                                size="small"
                                onChange={(e) => props.setProfile(e.target.value)}
                            >
                                <MenuItem value={"public"}>public</MenuItem>
                                <MenuItem value={"acyu"}>acyu</MenuItem>
                                <MenuItem value={"other"}>other</MenuItem>
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
                                        value={props.program}
                                        label="Program"
                                        size="small"
                                        onChange={(e) => props.setProgram(e.target.value)}
                                    >
                                        <MenuItem value={"Keysight_IdVgs"}>Keysight_IdVgs</MenuItem>
                                        <MenuItem value={"Keysight_IdVds"}>Keysight_IdVds</MenuItem>
                                    </Select>
                                </FormControl>
                                <CodeMirror
                                    value={props.config}
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
