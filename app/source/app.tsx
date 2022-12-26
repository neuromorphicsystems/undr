import * as React from "react";
import * as ReactDOM from "react-dom/client";
import styled, { ThemeProvider, createGlobalStyle } from "styled-components";
import { usePreferences } from "./hooks/preferences";

const GlobalStyle = createGlobalStyle`
    body {
        background-color: ${props => props.theme.background2};
    }
`;

const StyledMain = styled.div`
    display: flex;
    flex-direction: column;
    height: max(100vh, 500px);
    background-color: ${props => props.theme.background0};
    font-family: Helvetica, Arial, sans-serif;
    font-size: 14px;
    font-weight: 300;
    color: ${props => props.theme.content0};
`;

function Main() {
    const [preferences, setPreferences] = usePreferences();
    return (
        <ThemeProvider theme={preferences.theme}>
            <GlobalStyle />
            (preferences.loaded && <StyledMain></StyledMain>)
        </ThemeProvider>
    );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <Main />
);
