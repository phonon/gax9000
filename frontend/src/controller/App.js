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
      "step": 0.1,
  },
  "v_ds": [-0.05, -0.4, -1.2],
}`;

function App({
    axios, // axios instance
}) {
    const [gpibB1500, setGpibB1500] = useState(16);
    const [gpibCascade, setGpibCascade] = useState(22);
    const [measurementProfile, setMeasurementProfile] = useState("public");
    const [measurementProgram, setMeasurementProgram] = useState("");
    const [measurementConfig, setMeasurementConfig] = useState(DEFAULT_MEASUREMENT_CONFIG);

    useEffect(() => {
        axios.get("api/controller").then(response => {
            console.log("SUCCESS", response)
        }).catch(error => {
            console.log(error)
        })
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
                                    setAddress={setGpibB1500}
                                    identification=" "
                                    addressRange={GPIB_ADDRESS_RANGE}
                                    connectMsg={"connect_b1500"}
                                    disconnectMsg={"disconnect_b1500"}
                                />
                            </Grid>

                            <Grid item xs={6}>
                                <InstrumentConnection
                                    axios={axios}
                                    label="Cascade Probe Station"
                                    address={gpibCascade}
                                    setAddress={setGpibCascade}
                                    identification=" "
                                    addressRange={GPIB_ADDRESS_RANGE}
                                    connectMsg={"connect_cascade"}
                                    disconnectMsg={"disconnect_cascade"}
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
                    />
                </Grid>

                <Grid item sx={{width: "100%"}}>
                    <Divider/>
                </Grid>

                <Grid item sx={{width: "100%"}}>
                    <MeasurementControls
                        profile={measurementProfile}
                        setProfile={setMeasurementProfile}
                        program={measurementProgram}
                        setProgram={setMeasurementProgram}
                        config={measurementConfig}
                        setConfig={setMeasurementConfig}
                    />
                </Grid>
            </Grid>
        </Container>
    );
}

export default App;