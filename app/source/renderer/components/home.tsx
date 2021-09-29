import React from "react";
import styled from "styled-components";
import type { State } from "../../common/types";
import Dataset from "./dataset";
import Add from "../icons/add.svg";
import Bibtex from "../icons/bibtex.svg";
import Directory from "../icons/directory.svg";
import Download from "../icons/download.svg";

type Props = {
    state: State;
};

const Home = styled.div`
    overflow: hidden;
    flex-grow: 1;
    background-color: ${props => props.theme.background1};
    display: flex;
    flex-direction: column;
    justify-content: space-between;
`;

const Title = styled.div`
    width: 100%;
    height: 52px;
    padding-left: 13px;
    flex-shrink: 0;
    display: flex;
    gap: 20px;
    flex-direction: row;
    justify-content: space-between;
    font-size: 15px;
    align-items: center;
    color: ${props => props.theme.content1};
    border-bottom: 1px solid ${props => props.theme.backgroundSeparator};
    background-color: ${props => props.theme.background2};
`;

const DirectoryName = styled.div`
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    color: ${props => props.theme.content1};
    text-decoration: underline;
    text-decoration-color: transparent;
    transition: text-decoration-color 0.2s;
`;

const DirectoryLink = styled.div`
    overflow: hidden;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    & svg {
        height: 25px;
        position: relative;
        flex-shrink: 0;
    }
    & path {
        transition: fill 0.2s;
        fill: ${props => props.theme.content1};
    }
    &:hover ${DirectoryName} {
        text-decoration-color: ${props => props.theme.content1};
    }
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

const OpenDirectoryButton = styled(Button)`
    border-left: 1px solid ${props => props.theme.backgroundSeparator};
`;

const Datasets = styled.div`
    width: 100%;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    background-color: red;
`;

const Filler = styled.div`
    height: 50px;
    flex-shrink: 0;
    flex-grow: 1;
    &:nth-child(odd) {
        background-color: ${props => props.theme.background1};
    }
    &:nth-child(even) {
        background-color: ${props => props.theme.background2};
    }
`;

const ActionBar = styled.div`
    width: 100%;
    height: 52px;
    flex-shrink: 0;
    display: flex;
    border-top: 1px solid ${props => props.theme.backgroundSeparator};
    background-color: ${props => props.theme.background2};
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

export default function (props: Props) {
    return (
        <Home>
            <Title>
                <DirectoryLink onClick={() => window.undr.directory.show()}>
                    <Directory />
                    <DirectoryName>{props.state.directory}</DirectoryName>
                </DirectoryLink>
                <OpenDirectoryButton
                    $disabled={props.state.action != null}
                    onClick={() => {
                        if (props.state.action == null) {
                            window.undr.directory.choose();
                        }
                    }}
                >
                    Open another directory...
                </OpenDirectoryButton>
            </Title>
            <Datasets>
                {props.state.datasets.map(dataset => (
                    <Dataset key={dataset.name} dataset={dataset} />
                ))}
                <Filler />
            </Datasets>
            <ActionBar>
                <ActionButton $disabled={props.state.action != null}>
                    <Add />
                    <span>Add dataset</span>
                </ActionButton>
                <ActionButton
                    $disabled={props.state.action != null}
                    onClick={() => {
                        window.undr.bibtex.export();
                    }}
                >
                    <Bibtex />
                    <span>Export BibTeX...</span>
                </ActionButton>
                <ActionButton $disabled={props.state.action != null}>
                    <Download />
                    <span>Download</span>
                </ActionButton>
            </ActionBar>
        </Home>
    );
}
