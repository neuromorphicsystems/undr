import * as React from "react";
import { useLocation } from "react-router-dom";
import styled from "styled-components";
import * as constants from "../hooks/constants";
import {
    StateContext,
    navigateToMainRoute,
    stateNavigate,
} from "../hooks/state";
import About from "../icons/about.svg";
import Gear from "../icons/gear.svg";
import UndrBar from "../icons/undr-bar.svg";

const StyledToolbar = styled.div`
    position: fixed;
    top: 0;
    left: 0;
    z-index: 100;
    width: 100%;
    height: ${constants.barHeight}px;
    background-color: ${props => props.theme.background2};
    display: flex;
`;

const Container = styled.div`
    width: 0;
    flex-grow: 1;
`;

const Location = styled.div`
    height: ${constants.barHeight}px;
    font-size: ${constants.locationSize}px;
    display: flex;
    align-items: center;
    padding-left: ${(constants.barHeight - constants.locationSize) / 2}px;
    color: ${props => props.theme.content0};
    user-select: none;
`;

const LogoWrapper = styled.div`
    flex-shrink: 0;
    width: ${constants.logoWidth}px;
    display: flex;
    justify-content: center;
    align-items: center;
    & > svg {
        width: ${constants.logoWidth}px;
    }
    & > svg path {
        fill: ${props => props.theme.content0};
    }
`;

const Buttons = styled.div`
    height: ${constants.barHeight}px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    padding-right: ${(constants.barHeight - constants.buttonHeight) / 2}px;
`;

const Button = styled.div`
    height: ${constants.buttonHeight}px;
    padding: ${(constants.buttonHeight - constants.buttonIconHeight) / 2}px;
    cursor: pointer;
    border-radius: ${constants.buttonHeight / 2}px;
    transition: background-color 0.2s;
    &:hover {
        background-color: ${props => props.theme.background3};
    }
    & > svg {
        height: ${constants.buttonIconHeight}px;
    }
    & > svg path {
        fill: ${props => props.theme.content0};
    }
`;

export default function Toolbar() {
    const location = useLocation();
    const [state, _] = React.useContext(StateContext);
    return (
        <StyledToolbar>
            <Container>
                <Location>
                    {location.pathname.length > 1
                        ? `${location.pathname
                              .charAt(1)
                              .toUpperCase()}${location.pathname.slice(2)}`
                        : location.pathname}
                </Location>
            </Container>
            <LogoWrapper>
                <UndrBar />
            </LogoWrapper>
            <Container>
                <Buttons>
                    <Button
                        onClick={() => {
                            if (location.pathname === "/about") {
                                navigateToMainRoute(state, {
                                    state: { pathname: location.pathname },
                                });
                            } else {
                                stateNavigate(state, "/about");
                            }
                        }}
                    >
                        <About />
                    </Button>
                    <Button
                        onClick={() => {
                            if (location.pathname === "/preferences") {
                                navigateToMainRoute(state, {
                                    state: { pathname: location.pathname },
                                });
                            } else {
                                stateNavigate(state, "/preferences");
                            }
                        }}
                    >
                        <Gear />
                    </Button>
                </Buttons>
            </Container>
        </StyledToolbar>
    );
}
