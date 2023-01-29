import * as React from "react";
import styled from "styled-components";
import * as constants from "../hooks/constants";
import { Dataset, DatasetMode } from "../hooks/state";
import Input, { StyledInput } from "./input";
import Select, { Dropdown } from "./select";
import NumberInputWitDefault from "./numberInputWithDefault";
import Edit from "../icons/edit.svg";

interface DatasetProps {
    dataset: Dataset;
    datasetsNames: string[];
    datasetsNamesIndex: number;
    edit: boolean;
    showDelete: boolean;
    onChange: (dataset: Dataset) => void;
    onDelete: () => void;
    onCancel: () => void;
}

interface EditInterface {
    readonly edit: boolean;
}

const StyledDataset = styled.div<EditInterface>`
    height: ${props => (props.edit ? 265 : constants.barHeight)}px;
    background-color: ${props =>
        props.edit ? props.theme.background1 : props.theme.background0};
    transition: height ${constants.transitionDuration}s,
        background-color ${constants.transitionDuration}s;
    border-bottom: 1px solid ${props => props.theme.background3};
    overflow: hidden;
`;

const Property = styled.div`
    margin-bottom: 20px;
    & > ${StyledInput} {
        width: 100%;
    }
`;

const PropertyName = styled.div`
    user-select: auto;
    padding-left: 5px;
    padding-top: 13px;
    padding-bottom: 10px;
    color: ${props => props.theme.content1};
`;

const TimeoutLabel = styled(PropertyName)`
    padding-bottom: 5px;
`;

const Container = styled.div<EditInterface>`
    display: flex;
    align-items: top;
    justify-content: space-between;
    gap: 20px;
    padding-left: ${(constants.barHeight - constants.locationSize) / 2}px;
    padding-right: ${props =>
        props.edit
            ? (constants.barHeight - constants.locationSize) / 2
            : (constants.barHeight - constants.buttonHeight) / 2}px;
`;

const Left = styled.div`
    flex-grow: 1;
    overflow: hidden;
`;

const Right = styled.div<EditInterface>`
    flex-grow: 1;
    flex-shrink: 0;
    & ${Property} {
        padding-top: ${props => (props.edit ? 0 : 10)}px;
    }
    & ${Dropdown} {
        background-color: ${props =>
            props.edit ? props.theme.background0 : props.theme.background1};
    }
`;

const Line = styled.div<EditInterface>`
    display: flex;
    align-items: top;
    gap: 10px;
    justify-content: ${props => (props.edit ? "flex-start" : "flex-end")};
`;

interface NameInterface {
    readonly mode: DatasetMode;
}

const Name = styled.div<NameInterface>`
    height: ${constants.barHeight - 1}px;
    line-height: ${constants.barHeight - 1}px;
    font-weight: 500;
    user-select: auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: ${props => {
        switch (props.mode) {
            case "disabled":
                return props.theme.disabled;
            case "remote":
                return props.theme.remote;
            case "local":
                return props.theme.local;
            case "raw":
                return props.theme.raw;
        }
    }};
`;

const Button = styled.div`
    height: ${constants.buttonHeight}px;
    padding: ${(constants.buttonHeight - constants.buttonIconHeight) / 2}px;
    cursor: pointer;
    margin-top: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    border-radius: ${constants.buttonHeight / 2}px;
    transition: background-color 0.2s;
    &:hover {
        background-color: ${props => props.theme.background1};
    }
    & > svg {
        height: ${constants.buttonIconHeight}px;
    }
    & > svg path {
        fill: ${props => props.theme.content0};
    }
`;

const Actions = styled.div`
    display: flex;
    align-items: center;
    justify-content: space-evenly;
    gap: 20px;
    padding-left: 20px;
    padding-right: 20px;
`;

interface ActionInterface {
    readonly enabled: boolean;
}

const Action = styled.div`
    width: 100%;
    padding: 10px;
    height: 30px;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 5px;
    cursor: pointer;
    transition: border 0.2s, background-color 0.2s, color 0.2s;
    text-align: center;
`;

interface VisibleInterface {
    readonly visible: boolean;
}

const DeleteAction = styled(Action)<VisibleInterface>`
    background-color: ${props => props.theme.error};
    color: ${props => props.theme.background0};
    border: 1px solid ${props => props.theme.error};
    visibility: ${props => (props.visible ? "auto" : "hidden")};
    &:hover {
        color: ${props => props.theme.background0};
        background-color: ${props => props.theme.errorActive};
        border: 1px solid ${props => props.theme.errorActive};
    }
`;

const CancelAction = styled(Action)`
    color: ${props => props.theme.link};
    border: 1px solid ${props => props.theme.link};
    &:hover {
        color: ${props => props.theme.background0};
        background-color: ${props => props.theme.link};
        border: 1px solid ${props => props.theme.link};
    }
`;

const SaveAction = styled(Action)<ActionInterface>`
    color: ${props => props.theme.background0};
    background-color: ${props =>
        props.enabled ? props.theme.link : props.theme.background3};
    border: 1px solid
        ${props => (props.enabled ? props.theme.link : props.theme.background3)};
    &:hover {
        background-color: ${props =>
            props.enabled ? props.theme.linkActive : props.theme.background3};
        border: 1px solid
            ${props =>
                props.enabled
                    ? props.theme.linkActive
                    : props.theme.background3};
    }
    cursor: ${props => (props.enabled ? "pointer" : "auto")};
`;

export default function Dataset(props: DatasetProps) {
    const [edit, setEdit] = React.useState(props.edit);
    const [dataset, setDataset] = React.useState(props.dataset);
    const [timeoutValid, setTimeoutValid] = React.useState(true);
    React.useEffect(() => {
        setDataset(props.dataset);
    }, [props.dataset]);
    return (
        <StyledDataset edit={edit}>
            <Container edit={edit}>
                {edit ? (
                    <Left>
                        <Property>
                            <PropertyName>Name</PropertyName>
                            <Input
                                value={dataset.name}
                                onChange={name =>
                                    setDataset({
                                        ...dataset,
                                        name,
                                    })
                                }
                                error={
                                    props.datasetsNames.some(
                                        (name, index) =>
                                            index !==
                                                props.datasetsNamesIndex &&
                                            name === dataset.name
                                    ) ||
                                    !constants.namePattern.test(dataset.name)
                                }
                                live={true}
                                enabled={true}
                            />
                        </Property>
                        <Property>
                            <PropertyName>URL</PropertyName>
                            <Input
                                value={dataset.url}
                                onChange={url =>
                                    setDataset({
                                        ...dataset,
                                        url,
                                    })
                                }
                                error={!constants.urlPattern.test(dataset.url)}
                                live={true}
                                enabled={true}
                            />
                        </Property>
                    </Left>
                ) : (
                    <Left>
                        <Name mode={props.dataset.mode}>
                            {props.dataset.name}
                        </Name>
                    </Left>
                )}
                <Right edit={edit}>
                    <Line edit={edit}>
                        <Property>
                            {edit && <PropertyName>Mode</PropertyName>}
                            <Select
                                options={[
                                    ["disabled", "Disabled"],
                                    ["remote", "Remote"],
                                    ["local", "Local"],
                                    ["raw", "Raw"],
                                ]}
                                value={edit ? dataset.mode : props.dataset.mode}
                                onChange={mode => {
                                    if (edit) {
                                        setDataset({
                                            ...dataset,
                                            mode: mode as DatasetMode,
                                        });
                                    } else {
                                        props.onChange({
                                            ...props.dataset,
                                            mode: mode as DatasetMode,
                                        });
                                    }
                                }}
                            />
                        </Property>
                        {!edit && (
                            <Button
                                onClick={() => {
                                    setDataset(props.dataset);
                                    setEdit(true);
                                    setTimeoutValid(true);
                                }}
                            >
                                <Edit />
                            </Button>
                        )}
                    </Line>
                    {edit && (
                        <Property>
                            <TimeoutLabel>Timeout</TimeoutLabel>
                            <NumberInputWitDefault
                                defaultEnabled={dataset.timeout == null}
                                value={
                                    dataset.timeout == null
                                        ? constants.defaultTimeout
                                        : dataset.timeout
                                }
                                defaultValue={constants.defaultTimeout}
                                integer={false}
                                mustBeLargerThanZero={"yes-strict"}
                                unit={"s"}
                                onChange={(
                                    defaultEnabled: boolean,
                                    value: number
                                ) => {
                                    setDataset({
                                        ...dataset,
                                        timeout: defaultEnabled ? null : value,
                                    });
                                }}
                                onErrorChange={error => setTimeoutValid(!error)}
                            />
                        </Property>
                    )}
                </Right>
            </Container>
            {edit && (
                <Actions>
                    <DeleteAction
                        visible={props.showDelete}
                        onClick={() => props.onDelete()}
                    >
                        Delete
                    </DeleteAction>
                    <CancelAction
                        onClick={() => {
                            setDataset(props.dataset);
                            setEdit(false);
                            setTimeoutValid(true);
                            props.onCancel();
                        }}
                    >
                        Cancel
                    </CancelAction>
                    <SaveAction
                        enabled={
                            props.datasetsNames.every(
                                (name, index) =>
                                    index === props.datasetsNamesIndex ||
                                    name !== dataset.name
                            ) &&
                            constants.namePattern.test(dataset.name) &&
                            constants.urlPattern.test(dataset.url) &&
                            timeoutValid
                        }
                        onClick={() => {
                            if (
                                props.datasetsNames.every(
                                    (name, index) =>
                                        index === props.datasetsNamesIndex ||
                                        name !== dataset.name
                                ) &&
                                constants.namePattern.test(dataset.name) &&
                                constants.urlPattern.test(dataset.url) &&
                                timeoutValid
                            ) {
                                props.onChange(dataset);
                                setEdit(false);
                            }
                        }}
                    >
                        Save
                    </SaveAction>
                </Actions>
            )}
        </StyledDataset>
    );
}
