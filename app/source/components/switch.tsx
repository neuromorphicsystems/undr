import * as React from "react";
import styled from "styled-components";

interface SwitchProps {
    value: boolean;
    onChange: (newValue: boolean) => void;
}

const StyledSwitch = styled.div`
    margin-top: 10px;
    margin-bottom: 10px;
    margin-left: 15px;
    margin-right: 15px;
    height: 20px;
    width: 30px;
    border-radius: 15px;
    cursor: pointer;
    position: relative;
`;

interface ComponentInterface {
    value: boolean;
}

const Track = styled.div<ComponentInterface>`
    position: absolute;
    top: 3px;
    width: 30px;
    height: 14px;
    border-radius: 7px;
    background-color: ${props =>
        props.value ? props.theme.link : props.theme.background0};
`;

const Shadow = styled.div<ComponentInterface>`
    position: absolute;
    opacity: 0;
    top: -10px;
    width: 40px;
    height: 40px;
    border-radius: 20px;
    background-color: ${props =>
        props.value ? props.theme.linkActive : props.theme.switchBackground};
    left: ${props => (props.value ? "5px" : "-15px")};
    transition: opacity 0.2s, background-color 0.2s, left 0.2s;
    ${StyledSwitch}:hover &, ${StyledSwitch}:active & {
        opacity: 0.2;
    }
`;

const Thumb = styled.div<ComponentInterface>`
    position: absolute;
    top: 0;
    width: 20px;
    height: 20px;
    border-radius: 10px;
    box-shadow: ${props => `0 0 5px ${props.theme.switchThumbShadow}`};
    background-color: ${props =>
        props.value ? props.theme.linkActive : props.theme.switchBackground};
    left: ${props => (props.value ? "15px" : "-5px")};
    transition: left 0.2s;
`;

export default function Switch(props: SwitchProps) {
    return (
        <StyledSwitch onClick={() => props.onChange(!props.value)}>
            <Track value={props.value} />
            <Shadow value={props.value} />
            <Thumb value={props.value} />
        </StyledSwitch>
    );
}
