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
import {isNumeric, isValidNumber} from "../../utils/utils.js";

/**
 * Wrapper for setting a user profile setting in backend
 * and local value in react app.
 * @param {Axios} axios - axios instance
 * @param {string} user - username of user
 * @param {string} setting - string name of setting in backend to set
 * @param {Function} type - javascript object type (e.g. Number of String)
 * @param {*} oldValue - old value for checking if value changed
 * @param {*} newValue - new input value in field
 * @param {function} setValueLocal - function to set local value
 */
const handleSetUserSetting = (axios, user, setting, type, oldValue, newValue, setValueLocal) => {
    // invalid user
    if ( user === "" ) {
        return
    }

    // only update if value actually changed
    if ( oldValue !== newValue ) {
        // parse new value and validate if correct
        let newValueParsed;
        let valid;
        if ( type === Number ) {
            newValueParsed = Number(newValue);
            valid = isValidNumber(newValueParsed);
        } else {
            newValueParsed = newValue;
            valid = true;
        }

        if ( valid ) {
            // push change to server
            axios.put("api/controller", {
                msg: "set_user_setting",
                data: {
                    user: user,
                    setting: setting,
                    value: newValueParsed,
                },
            });
        }

        // set local value to raw value (not parsed)
        // to avoid getting stuck with "NaN"
        setValueLocal(newValue);
    }
}

const handleMoveChuckRelative = (axios, dxExpr, dyExpr) => {
    // Parse dx_expr and dy_expr using `eval`.
    // This is to allow expressions like `10*240` to be used
    // since its convenient to be able to use expressions
    // when moving across a die (e.g. across an array of rows/cols).

    // try to eval, throw and print stacktrace if invalid
    let dx;
    let dy;
    try {
        dx = eval(dxExpr);
    } catch ( err ) {
        console.error(err);
        return;
    }

    try {
        dy = eval(dyExpr);
    } catch ( err ) {
        console.error(err);
        return;
    }

    console.log("dx", dx, "dy", dy);

    if ( isValidNumber(dx) && isValidNumber(dy) ) {
        axios.put("api/controller", {
            msg: "move_chuck_relative",
            data: {
                dx: dx,
                dy: dy,
            },
        });
    } else {
        console.error(`dx or dy is not a valid number: dx=${dx} (${typeof dx}), dy=${dy} (${typeof dy})`);
    }

}

/**
 * Wafer controller
 */
export const WaferControls = ({
    axios,
    user,
    dieSizeX,
    setDieSizeXLocal,
    dieSizeY,
    setDieSizeYLocal,
    dieOffsetX,
    setDieOffsetXLocal,
    dieOffsetY,
    setDieOffsetYLocal,
    currentDieX,
    setCurrentDieXLocal,
    currentDieY,
    setCurrentDieYLocal,
    deviceX,
    setDeviceXLocal,
    deviceY,
    setDeviceYLocal,
    deviceRow,
    setDeviceRowLocal,
    deviceCol,
    setDeviceColLocal,
}) => {
    return (
        <Box id="wafer-controls" sx={{width: "100%"}}>
            <Grid
                container
                spacing={1}
                direction="row"
            >
                {/* Wafer controls */}
                <Grid item xs={6}  align="center" sx={{width: "100%", height: "100%"}}>
                    <Box sx={{width: "100%"}}>
                        <Grid
                            container
                            direction="row"
                            spacing={1}
                            columns={12}
                        >
                            <Grid item xs={6}>
                                <Box sx={{
                                    width: "160px",
                                    height: "160px",
                                    backgroundColor: "rgba(0,0,0,0.05)",
                                    border: "1px solid grey",
                                    borderRadius: "50%",
                                }}/>
                            </Grid>

                            <Grid item xs={6}>
                                <Grid
                                    container
                                    direction="row"
                                    spacing={1}
                                    columns={12}
                                >
                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Die Size X"
                                            variant="outlined"
                                            size="small"
                                            value={dieSizeX}
                                            onChange={(e) => handleSetUserSetting(axios, user, "die_size_x", Number, dieSizeX, e.target.value, setDieSizeXLocal)}
                                            error={!isNumeric(dieSizeX)}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Die Size Y"
                                            variant="outlined"
                                            size="small"
                                            value={dieSizeY}
                                            onChange={(e) => handleSetUserSetting(axios, user, "die_size_y", Number, dieSizeY, e.target.value, setDieSizeYLocal)}
                                            error={!isNumeric(dieSizeY)}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Offset X"
                                            variant="outlined"
                                            size="small"
                                            value={dieOffsetX}
                                            onChange={(e) => handleSetUserSetting(axios, user, "die_offset_x", Number, dieOffsetX, e.target.value, setDieOffsetXLocal)}
                                            error={!isNumeric(dieOffsetX)}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Offset Y"
                                            variant="outlined"
                                            size="small"
                                            value={dieOffsetY}
                                            onChange={(e) => handleSetUserSetting(axios, user, "die_offset_y", Number, dieOffsetY, e.target.value, setDieOffsetYLocal)}
                                            error={!isNumeric(dieOffsetY)}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Current Die X"
                                            variant="outlined"
                                            size="small"
                                            value={currentDieX}
                                            onChange={(e) => handleSetUserSetting(axios, user, "current_die_x", Number, currentDieX, e.target.value, setCurrentDieXLocal)}
                                            error={!isNumeric(currentDieX)}
                                        />
                                    </Grid>

                                    <Grid item xs={6}>
                                        <TextField
                                            fullWidth
                                            label="Current Die Y"
                                            variant="outlined"
                                            size="small"
                                            value={currentDieY}
                                            onChange={(e) => handleSetUserSetting(axios, user, "current_die_y", Number, currentDieY, e.target.value, setCurrentDieYLocal)}
                                            error={!isNumeric(currentDieY)}
                                        />
                                    </Grid>

                                </Grid>
                            </Grid>
                        </Grid>
                        
                    </Box>
                    
                </Grid>

                {/* Die controls */}
                <Grid item xs={6} align="center" sx={{width: "100%"}}>
                    <Box sx={{width: "80%"}}>
                        <Grid
                            container
                            spacing={1}
                            columns={18}
                        >
                            {/* top row: dieY control */}
                            <Grid item xs={3}/>
                            <Grid item xs={6} align="center">
                                <TextField
                                    fullWidth
                                    label="Device Y"
                                    variant="outlined"
                                    size="small"
                                    value={deviceY}
                                    onChange={(e) => handleSetUserSetting(axios, user, "device_y", Number, deviceY, e.target.value, setDeviceYLocal)}
                                    error={!isNumeric(deviceY)}
                                />
                            </Grid>
                            <Grid item xs={9}/>
                            
                            {/* controls: top row */}
                            <Grid item xs={4}/>
                            <Grid item xs={4}>
                                <Button
                                    variant="outlined"
                                    color="primary"
                                    onClick={() => handleMoveChuckRelative(axios, "0", String(deviceY))}
                                >
                                    🡹
                                </Button>
                            </Grid>
                            <Grid item xs={10}/>

                            {/* controls: middle row */}
                            <Grid item xs={4}>
                                <Button
                                    variant="outlined"
                                    color="primary"
                                    onClick={() => handleMoveChuckRelative(axios, "-" + String(deviceX), "0")}
                                >
                                    🡸
                                </Button>
                            </Grid>

                            <Grid item xs={4}/>

                            <Grid item xs={4}>
                                <Button 
                                    variant="outlined"
                                    color="primary"
                                    onClick={() => handleMoveChuckRelative(axios, String(deviceX), "0")}
                                >
                                    🡺
                                </Button>
                            </Grid>

                            <Grid item xs={6}>
                                <TextField
                                    fullWidth
                                    label="Device X"
                                    variant="outlined"
                                    size="small"
                                    value={deviceX}
                                    onChange={(e) => handleSetUserSetting(axios, user, "device_x", Number, deviceX, e.target.value, setDeviceXLocal)}
                                    error={!isNumeric(deviceX)}
                                />
                            </Grid>

                            {/* controls: bottom row */}
                            <Grid item xs={4}/>
                            <Grid item xs={4}>
                                <Button
                                    variant="outlined"
                                    color="primary"
                                    onClick={() => handleMoveChuckRelative(axios, "0", "-" + String(deviceY))}
                                >
                                    🡻
                                </Button>
                            </Grid>
                            <Grid item xs={10}/>
                            
                            {/* device x/y: bottom row */}
                            <Grid item xs={6} align="center">
                                <TextField
                                    fullWidth
                                    label="Row"
                                    variant="outlined"
                                    size="small"
                                    value={deviceRow}
                                    onChange={(e) => handleSetUserSetting(axios, user, "device_row", Number, deviceRow, e.target.value, setDeviceRowLocal)}
                                    error={!isNumeric(deviceRow)}
                                />
                            </Grid>
                            <Grid item xs={6} align="center">
                                <TextField
                                    fullWidth
                                    label="Column"
                                    variant="outlined"
                                    size="small"
                                    value={deviceCol}
                                    onChange={(e) => handleSetUserSetting(axios, user, "device_col", Number, deviceCol, e.target.value, setDeviceColLocal)}
                                    error={!isNumeric(deviceCol)}
                                />
                            </Grid>
                            <Grid item xs={6}/>

                        </Grid>
                    </Box>
                </Grid>

            </Grid>
            
        </Box>
    );
}
