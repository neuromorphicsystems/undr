import React from "react";
import styled from "styled-components";
import type { State } from "../../common/types";
import Add from "../icons/add.svg";
import Bibtex from "../icons/bibtex.svg";
import Cancel from "../icons/cancel.svg";
import Install from "../icons/install.svg";

type Props = {
    state: State;
};

const Bar = styled.div`
    width: 100%;
    height: 52px;
    flex-shrink: 0;
    display: flex;
    border-top: 1px solid ${props => props.theme.backgroundSeparator};
    background-color: ${props => props.theme.background2};
`;

const Button = styled.div<{ $disabled: boolean }>`
    height: 51px;
    line-height: 51px;
    flex-shrink: 0;
    background-color: ${props => props.theme.background2};
    color: ${props =>
        props.$disabled ? props.theme.content2 : props.theme.content1};
    font-size: 15px;
    padding-left: 15px;
    padding-right: 15px;
    cursor: ${props => (props.$disabled ? "default" : "pointer")};
    transition: background-color 0.2s;
    text-align: center;
    &:hover {
        background-color: ${props =>
            props.$disabled
                ? props.theme.background2
                : props.theme.background1};
    }
    user-select: none;
`;

const ErrorBar = styled(Bar)`
    padding-left: 10px;
    gap: 20px;
    background-color: ${props => props.theme.error};
`;

const Error = styled.div`
    height: 100%;
    flex-grow: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
    color: ${props => props.theme.titleBarContent};
`;

const DismissButton = styled(Button)`
    width: 196px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    border-left: 1px solid ${props => props.theme.backgroundSeparator};
    background-color: ${props => props.theme.error};
    color: ${props => props.theme.titleBarContent};
    &:hover {
        background-color: ${props => props.theme.errorActive};
    }
    & svg {
        height: 25px;
        position: relative;
        flex-shrink: 0;
    }
    & path {
        fill: ${props => props.theme.titleBarContent};
    }
`;

const ActionBar = styled(Bar)`
    justify-content: space-between;
    & > ${Button} {
        flex-grow: 1;
    }
`;

const ActionButton = styled(Button)`
    flex-basis: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    &:not(:last-of-type) {
        border-right: 1px solid ${props => props.theme.backgroundSeparator};
    }
    & svg {
        height: 25px;
        position: relative;
        flex-shrink: 0;
    }
    & path {
        fill: ${props =>
            props.$disabled ? props.theme.content2 : props.theme.content1};
    }
`;

const StatusBar = styled(Bar)`
    padding-left: 10px;
    gap: 20px;
`;

const CancelButton = styled(Button)`
    width: 196px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    border-left: 1px solid ${props => props.theme.backgroundSeparator};
    & svg {
        height: 25px;
        position: relative;
        flex-shrink: 0;
    }
    & path {
        fill: ${props =>
            props.$disabled ? props.theme.content2 : props.theme.content1};
    }
`;

const Status = styled.div`
    height: 100%;
    flex-grow: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
`;

const StatusAction = styled.div`
    flex-shrink: 0;
    height: 17px;
    font-size: 14px;
    color: ${props => props.theme.content1};
`;

const StatusDetails = styled.div`
    flex-shrink: 0;
    height: 17px;
    font-size: 14px;
    color: ${props => props.theme.content2};
`;

const stateToStatusAction = (state: State): string => {
    let result = "";
    switch (state.action) {
        case "init":
            result += "Creating a new configuration";
            break;
        case "install":
            result += "Installing datasets";
            break;
        case "bibtex":
            result += "Exporting Bibtex";
            break;
        default:
            result += state.action;
    }
    if (state.phase != null) {
        switch (state.phase.name) {
            default:
                result += " - " + state.phase.name;
        }
        if (state.phase.count > 1) {
            result += ` (step ${state.phase.index + 1} of ${
                state.phase.count
            })`;
        }
    }
    return result;
};

export default function (props: Props) {
    if (props.state.error != null) {
        return (
            <ErrorBar>
                <Error>{props.state.error}</Error>
                <DismissButton
                    $disabled={false}
                    onClick={() => {
                        window.undr.state.clearError();
                    }}
                >
                    <Cancel />
                    <span>Dismiss</span>
                </DismissButton>
            </ErrorBar>
        );
    }
    if (props.state.action != null) {
        return (
            <StatusBar>
                <Status>
                    <StatusAction>
                        {stateToStatusAction(props.state)}
                    </StatusAction>
                    <StatusDetails>{props.state.details}</StatusDetails>
                </Status>
                {props.state.action !== "init" && (
                    <CancelButton
                        $disabled={false}
                        onClick={() => {
                            window.undr.interface.cancel();
                        }}
                    >
                        <Cancel />
                        <span>Cancel</span>
                    </CancelButton>
                )}
            </StatusBar>
        );
    }
    return (
        <ActionBar>
            <ActionButton $disabled={false}>
                <Add />
                <span>Add dataset</span>
            </ActionButton>
            <ActionButton
                $disabled={false}
                onClick={() => {
                    window.undr.bibtex.export();
                }}
            >
                <Bibtex />
                <span>Export BibTeX...</span>
            </ActionButton>
            <ActionButton $disabled={false}>
                <Install />
                <span>Install</span>
            </ActionButton>
        </ActionBar>
    );
}
