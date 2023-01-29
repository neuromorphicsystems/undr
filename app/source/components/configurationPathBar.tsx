import * as React from "react";
import { invoke } from "@tauri-apps/api";
import { message, open } from "@tauri-apps/api/dialog";
import styled from "styled-components";
import * as constants from "../hooks/constants";
import { PreferencesContext } from "../hooks/preferences";
import Expand from "../icons/expand.svg";

interface ConfigurationPathBarProps {
    path: string;
    menu: boolean;
}

interface MenuInterface {
    readonly menu: boolean;
}

const Bar = styled.div<MenuInterface>`
    height: ${constants.barHeight}px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    padding-left: ${(constants.barHeight - constants.locationSize) / 2}px;
    padding-right: ${props =>
        props.menu
            ? (constants.barHeight - constants.buttonHeight) / 2
            : (constants.barHeight - constants.locationSize) / 2}px;
    background-color: ${props => props.theme.background1};
`;

interface ShowMenuInterface {
    readonly showMenu: boolean;
}

const Button = styled.div<ShowMenuInterface>`
    flex-shrink: 0;
    height: ${constants.buttonHeight}px;
    padding: ${(constants.buttonHeight - constants.buttonIconHeight) / 2}px;
    cursor: pointer;
    border-radius: ${constants.buttonHeight / 2}px;
    transition: background-color 0.2s;
    background-color: ${props =>
        props.showMenu ? props.theme.background2 : props.theme.background1};
    &:hover {
        background-color: ${props => props.theme.background2};
    }
    & > svg {
        height: ${constants.buttonIconHeight}px;
    }
    & > svg path {
        fill: ${props => props.theme.content0};
    }
`;

const ConfigurationPath = styled.div`
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    user-select: auto;
    cursor: pointer;
    &:hover {
        text-decoration: underline;
        color: ${props => props.theme.content1};
    }
`;

const MenuOverlay = styled.div`
    position: absolute;
    z-index: 1;
    top: 0;
    left: 0;
    width: 100vw;
    height: calc(100vh - ${constants.barHeight}px);
`;

const Menu = styled.div`
    position: absolute;
    z-index: 2;
    top: ${constants.barHeight - 5}px;
    right: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    background-color: ${props => props.theme.background2};
    border: 1px solid ${props => props.theme.background3};
    display: flex;
    flex-direction: column;
    border-radius: ${constants.buttonHeight / 4}px;
    overflow: hidden;
`;

const MenuItem = styled.div`
    font-weight: 500;
    cursor: pointer;
    padding: 10px;
    &:hover {
        background-color: ${props => props.theme.background3};
    }
`;

export default function ConfigurationPathBarInterface(
    props: ConfigurationPathBarProps
) {
    const [preferences, setStoredPreferences] =
        React.useContext(PreferencesContext);
    const [showMenu, setShowMenu] = React.useState(false);
    return (
        <>
            <Bar menu={props.menu}>
                <ConfigurationPath
                    onClick={() => {
                        invoke("reveal_in_os", {
                            path: props.path,
                        }).catch(error => {
                            console.error(error);
                            message(JSON.stringify(error), {
                                title: "Error",
                                type: "error",
                            });
                        });
                    }}
                >
                    {props.path}
                </ConfigurationPath>
                {props.menu && (
                    <Button
                        showMenu={showMenu}
                        onClick={() => setShowMenu(!showMenu)}
                    >
                        <Expand />
                    </Button>
                )}
            </Bar>
            {props.menu && showMenu && (
                <MenuOverlay onClick={() => setShowMenu(false)}>
                    <Menu>
                        <MenuItem
                            onClick={() => {
                                invoke("create_configuration", {
                                    content: UNDR_DEFAULT_TOML,
                                })
                                    .then(configurationPath => {
                                        if (configurationPath != null) {
                                            setStoredPreferences({
                                                ...preferences.storedPreferences,
                                                configurationPath:
                                                    configurationPath as string,
                                            });
                                        }
                                    })
                                    .catch(error => {
                                        console.error(error);
                                        message(JSON.stringify(error), {
                                            title: "Error",
                                            type: "error",
                                        });
                                    });
                            }}
                        >
                            New configuration...
                        </MenuItem>
                        <MenuItem
                            onClick={() => {
                                open({
                                    title: "Open configuration",
                                    multiple: false,
                                    filters: [
                                        {
                                            name: "configuration",
                                            extensions: ["toml"],
                                        },
                                    ],
                                })
                                    .then(configurationPath => {
                                        if (
                                            configurationPath != null &&
                                            configurationPath.length > 0
                                        ) {
                                            setStoredPreferences({
                                                ...preferences.storedPreferences,
                                                configurationPath:
                                                    configurationPath as string,
                                            });
                                        }
                                    })
                                    .catch(error => {
                                        console.error(error);
                                        message(JSON.stringify(error), {
                                            title: "Error",
                                            type: "error",
                                        });
                                    });
                            }}
                        >
                            Open configuration...
                        </MenuItem>
                    </Menu>
                </MenuOverlay>
            )}
        </>
    );
}
