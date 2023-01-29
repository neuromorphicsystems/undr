import * as React from "react";
import * as ReactDOM from "react-dom/client";
import {
    createBrowserRouter,
    RouterProvider,
    useLocation,
    useOutlet,
    useNavigate,
} from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import styled, { ThemeProvider, createGlobalStyle } from "styled-components";
import { usePreferences, PreferencesContext } from "./hooks/preferences";
import { useState, StateContext, navigateToMainRoute } from "./hooks/state";
import About from "./components/about";
import Datasets from "./components/datasets";
import ActionDisplay from "./components/actionDisplay";
import Preferences from "./components/preferences";
import Setup from "./components/setup";
import Toolbar from "./components/toolbar";

const GlobalStyle = createGlobalStyle`
    body {
        background-color: ${props => props.theme.background0};
        user-select: none;
    }
`;

const StyledMain = styled.div`
    height: 100vh;
    background-color: ${props => props.theme.background0};
    font-family: Helvetica, Arial, sans-serif;
    font-size: 14px;
    font-weight: 300;
    color: ${props => props.theme.content0};
`;

function AnimatedOutlet() {
    const outlet = useOutlet();
    const [frozenOutlet] = React.useState(outlet);
    return <>{frozenOutlet}</>;
}

const Content = styled.div`
    position: absolute;
    left: 0;
    right: 0;
    top: 51px;
    bottom: 0;
    overflow: hidden;
`;

function AnimatedContainer() {
    const location = useLocation();
    const [_, dispatchStateAction] = React.useContext(StateContext);
    const navigate = useNavigate();
    React.useEffect(() => {
        dispatchStateAction({
            type: "navigate",
            payload: navigate,
        });
    }, []);
    return (
        <>
            <Toolbar />
            <Content>
                <AnimatePresence>
                    <AnimatedOutlet key={location.pathname} />
                </AnimatePresence>
            </Content>
        </>
    );
}

function RedirectMain() {
    const [state, _] = React.useContext(StateContext);
    React.useEffect(() => {
        if (state.loaded && state.navigateFunction != null) {
            navigateToMainRoute(state);
        }
    }, [state.loaded, state.navigateFunction]);
    return <></>;
}

const router = createBrowserRouter([
    {
        element: <AnimatedContainer />,
        children: [
            {
                path: "/",
                element: <RedirectMain />,
            },
            {
                path: "/setup",
                element: <Setup />,
            },
            {
                path: "/datasets",
                element: <Datasets />,
            },
            {
                path: "/action",
                element: <ActionDisplay />,
            },
            {
                path: "/about",
                element: <About />,
            },
            {
                path: "/preferences",
                element: <Preferences />,
            },
        ],
    },
]);

function Main() {
    const [preferences, setPreferences, setStoredPreferences] =
        usePreferences();
    const [state, dispatchStateAction] = useState(setPreferences);
    return (
        <PreferencesContext.Provider
            value={[preferences, setStoredPreferences]}
        >
            <StateContext.Provider value={[state, dispatchStateAction]}>
                <ThemeProvider theme={preferences.theme}>
                    <GlobalStyle />
                    <StyledMain>
                        <RouterProvider router={router} />
                    </StyledMain>
                </ThemeProvider>
            </StateContext.Provider>
        </PreferencesContext.Provider>
    );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <Main />
);
