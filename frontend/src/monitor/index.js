import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import Plot from "react-plotly.js";

const Monitor = () => {
    let [x, setX] = useState([0, 1, 2, 3])
    let [y, setY] = useState([3, 2, 1, 0])

    useEffect(() => {
        var eventSrc = new EventSource("http://localhost:5000/subscribe");
        eventSrc.onmessage = (e) => {
            console.log(e.data);
            const data = JSON.parse(e.data);
            console.log(data);
            setX(data.x);
            setY(data.y);
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
        <div>
            <Plot
                data={[
                {
                    x: x,
                    y: y,
                    type: 'scatter',
                    mode: 'lines+markers',
                    marker: {color: 'red'},
                },
                ]}
                layout={ {width: 600, height: 400, title: 'A Fancy Plot'} }
            />
        </div>
    )
}

ReactDOM.render(
  <React.StrictMode>
    <Monitor/>
  </React.StrictMode>,
  document.getElementById("root")
);
