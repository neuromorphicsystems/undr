import React from "react";
import { useRouteMatch, Link } from "react-router-dom";
import styled from "styled-components";
import About from "../icons/about.svg";
import Gear from "../icons/gear.svg";
import TitleBarLogo from "../icons/titleBarLogo.svg";

const TitleBar = styled.div`
    flex-shrink: 0;
    position: relative;
    background-color: ${props => props.theme.titleBarBackground};
    -webkit-user-select: none;
    user-select: none;
    -webkit-app-region: drag;
    height: 52px;
    padding-left: 11px;
    padding-right: 11px;
    display: flex;
    align-items: center;
    justify-content: space-between;
`;

const Placeholder = styled.div`
    order: ${() => (window.undr.platform === "darwin" ? "0" : "2")};
    width: 71px;
    height: 30px;
`;

const Logo = styled.div`
    height: 40px;
    order: 1;
    & > svg {
        height: 40px;
    }
    & > svg path {
        fill: ${props => props.theme.titleBarContent};
    }
`;

const Buttons = styled.div`
    order: ${() => (window.undr.platform === "darwin" ? "2" : "0")};
    display: flex;
    gap: 11px;
`;

const Button = styled(Link)<{ $active: boolean }>`
    width: 30px;
    height: 30px;
    padding: 3px;
    text-decoration: none;
    background-color: ${props => props.theme.titleBarContent}${props => (props.$active ? "ff" : "00")};
    transition: background-color 0.2s;
    border-radius: 5px;
    &:hover {
        background-color: ${props => props.theme.titleBarContent}${props => (props.$active ? "bb" : "44")};
    }
    & path {
        fill: ${props =>
            props.$active
                ? props.theme.titleBarBackground
                : props.theme.titleBarContent};
    }
`;

export default function () {
    const settingsMatch = useRouteMatch("/settings");
    const aboutMatch = useRouteMatch("/about");
    return (
        <TitleBar>
            <Buttons>
                <Button
                    to={settingsMatch ? "/" : "/settings"}
                    $active={settingsMatch != null}
                >
                    <Gear />
                </Button>
                <Button
                    to={aboutMatch ? "/" : "/about"}
                    $active={aboutMatch != null}
                >
                    <About />
                </Button>
            </Buttons>
            <Logo>
                <TitleBarLogo />
            </Logo>
            <Placeholder />
        </TitleBar>
    );
}
