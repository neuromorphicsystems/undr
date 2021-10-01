import React, { useEffect, useState } from "react";
import {
    HashRouter as Router,
    Redirect,
    Switch,
    Route,
} from "react-router-dom";
import styled, { ThemeProvider } from "styled-components";
import type { Theme } from "../../common/types";
import { dark, light } from "../theme";
import Home from "./home";
import Settings from "./settings";
import TitleBar from "./titleBar";
import Welcome from "./welcome";

const StyledApplication = styled.div`
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
`;

export default function () {
    const [shouldUseDarkColors, setShouldUseDarkColors] = useState(
        window.undr.theme.shouldUseDarkColors()
    );
    useEffect(() => {
        window.undr.theme.onShouldUseDarkColorsUpdate(setShouldUseDarkColors);
        return () => {
            window.undr.theme.offShouldUseDarkColorsUpdate(
                setShouldUseDarkColors
            );
        };
    }, []);
    const [themeName, setThemeName] = useState(
        window.undr.theme.load() || "System default"
    );
    const [timeout, setTimeout] = useState(window.undr.timeout.load() || 60);
    const [workersCount, setWorkersCount] = useState(
        window.undr.workersCount.load() || 32
    );
    const [state, setState] = useState(window.undr.state.load());
    useEffect(() => {
        window.undr.state.onUpdate(setState);
        return () => {
            window.undr.state.offUpdate(setState);
        };
    }, []);
    return (
        <ThemeProvider
            theme={((
                themeName: string,
                shouldUseDarkColors: boolean
            ): Theme => {
                switch (themeName) {
                    case "System default":
                        return shouldUseDarkColors ? dark : light;
                    case "Light":
                        return light;
                    case "Dark":
                        return dark;
                    default:
                        throw new Error(`unknown theme name ${themeName}`);
                }
            })(themeName, shouldUseDarkColors)}
        >
            <StyledApplication>
                <Router>
                    <TitleBar />
                    <Switch>
                        <Route path="/about"></Route>
                        <Route path="/settings">
                            <Settings
                                themeName={themeName}
                                onThemeNameChange={newThemeName => {
                                    window.undr.theme.store(newThemeName);
                                    setThemeName(newThemeName);
                                }}
                                timeout={timeout}
                                onTimeoutChange={newTimeout => {
                                    window.undr.timeout.store(newTimeout);
                                    setTimeout(newTimeout);
                                }}
                                workersCount={workersCount}
                                onWorkersCountChange={newWorkersCount => {
                                    window.undr.workersCount.store(
                                        newWorkersCount
                                    );
                                    setWorkersCount(newWorkersCount);
                                }}
                            />
                        </Route>
                        <Route path="/welcome">
                            {state.directory != null ? (
                                <Redirect to="/" />
                            ) : (
                                <Welcome />
                            )}
                        </Route>
                        <Route path="/">
                            {state.directory == null ? (
                                <Redirect to="/welcome" />
                            ) : (
                                <Home state={state} />
                            )}
                        </Route>
                    </Switch>
                </Router>
            </StyledApplication>
        </ThemeProvider>
    );
}
