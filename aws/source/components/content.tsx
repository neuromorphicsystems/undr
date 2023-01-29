import * as React from "react";
import styled from "styled-components";
import useDimensions from "../hooks/dimensions";
import Spinner from "./spinner";
import Caret from "../icons/caret.svg";
import Directory from "../icons/directory.svg";
import File from "../icons/file.svg";

interface ContentProps {
    pathComponents: string[];
}

class DirectoryChild {
    name: string;
    constructor(name: string) {
        this.name = name;
    }
}

class FileChild {
    name: string;
    size: number;
    modified: Date;
    constructor(name: string, size: number, modified: Date) {
        this.name = name;
        this.size = size;
        this.modified = modified;
    }
}

enum Status {
    Loading = 0,
    Success = 1,
    Error = 2,
}

interface State {
    status: Status;
    children: (DirectoryChild | FileChild)[];
    error: string | null;
}

interface StyledContentProps {
    header: number;
}

const StyledContent = styled.div<StyledContentProps>`
    overflow: hidden;
    flex-grow: 1;
    display: grid;
    grid-template-columns: auto;
    grid-template-rows: ${props => props.header}px auto;
    grid-template-areas:
        "header"
        "body";
`;

const NameCell = styled.div`
    width: 0;
    flex-grow: 1;
    display: flex;
    padding-left: 15px;
    padding-right: 15px;
    align-items: center;
    & > svg {
        flex-shrink: 0;
        height: 24px;
        vertical-align: middle;
        padding-right: 10px;
        & > path {
            fill: ${props => props.theme.content0};
        }
    }
    & > a {
        flex-shrink: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        text-decoration: none;
        vertical-align: middle;
        color: ${props => props.theme.content0};
        font-weight: 500;
        text-decoration: none;
        &:hover,
        &:active {
            text-decoration: underline;
            color: ${props => props.theme.link};
        }
    }
`;

const SizeCell = styled.div`
    width: 120px;
    flex-shrink: 0;
    display: flex;
    padding-left: 15px;
    padding-right: 15px;
    align-items: center;
    color: ${props => props.theme.content0};
    font-weight: 300;
`;

const ModifiedCell = styled.div`
    width: 170px;
    flex-shrink: 0;
    display: flex;
    padding-left: 15px;
    padding-right: 15px;
    align-items: center;
    color: ${props => props.theme.content0};
    font-weight: 300;
    @media (max-width: 512px) {
        display: none;
    }
`;

const Body = styled.div`
    grid-area: body;
    overflow-y: auto;
`;

const Loading = styled.div`
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100%;
`;

interface ChildrenProps {
    visible: boolean;
}

const Children = styled.div<ChildrenProps>`
    display: ${props => (props.visible ? "block" : "none")};
    @media (max-width: 512px) {
        padding-left: 0;
        padding-right: 0;
        padding-bottom: 0;
    }
`;

interface HeaderProps {
    visible: boolean;
    delta: number;
}

const Header = styled.div<HeaderProps>`
    grid-area: header;
    display: ${props => (props.visible ? "flex" : "none")};
    background-color: ${props => props.theme.background0};
    border-bottom: 1px solid ${props => props.theme.content2};
    padding-left: 15px;
    padding-right: ${props => props.delta + 15}px;
    @media (max-width: 512px) {
        padding-left: 0;
        padding-right: ${props => props.delta}px;
    }
`;

interface SortMethod {
    direction: -1 | 1;
    column: 0 | 1 | 2;
}

interface HeaderCellProps {
    sortMethod: SortMethod;
}

const HeaderCell = styled.div<HeaderCellProps>`
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-left: 15px;
    padding-right: 15px;
    cursor: pointer;
    &:hover,
    &:active {
        & > span {
            color: ${props => props.theme.content0};
        }
    }
    & > span {
        font-weight: 500;
    }
    & > svg {
        transform: rotate(
            ${props => (props.sortMethod.direction === 1 ? 0 : 180)}deg
        );
        flex-shrink: 0;
        height: 16px;
        vertical-align: middle;
        & > path {
            fill: ${props => props.theme.content0};
        }
    }
`;

const HeaderNameCell = styled(HeaderCell)`
    width: 0;
    flex-grow: 1;
    & > span {
        color: ${props =>
            props.sortMethod.column === 0
                ? props.theme.content0
                : props.theme.content1};
    }
    & > svg {
        display: ${props => (props.sortMethod.column === 0 ? "block" : "none")};
    }
`;

const HeaderSizeCell = styled(HeaderCell)`
    width: 120px;
    flex-shrink: 0;
    display: flex;
    padding-left: 15px;
    padding-right: 15px;
    align-items: center;
    font-weight: 300;
    position: relative;
    &:after {
        content: "";
        width: 1px;
        position: absolute;
        left: 0;
        top: 15px;
        bottom: 15px;
        background-color: ${props => props.theme.content2};
    }
    & > span {
        color: ${props =>
            props.sortMethod.column === 1
                ? props.theme.content0
                : props.theme.content1};
    }
    & > svg {
        display: ${props => (props.sortMethod.column === 1 ? "block" : "none")};
    }
`;

const HeaderModifiedCell = styled(HeaderCell)`
    width: 170px;
    flex-shrink: 0;
    display: flex;
    padding-left: 15px;
    padding-right: 15px;
    align-items: center;
    font-weight: 300;
    position: relative;
    &:after {
        content: "";
        width: 1px;
        position: absolute;
        left: 0;
        top: 15px;
        bottom: 15px;
        background-color: ${props => props.theme.content2};
    }
    & > span {
        color: ${props =>
            props.sortMethod.column === 2
                ? props.theme.content0
                : props.theme.content1};
    }
    & > svg {
        display: ${props => (props.sortMethod.column === 2 ? "block" : "none")};
    }
    @media (max-width: 512px) {
        display: none;
    }
`;

const Child = styled.div`
    display: flex;
    height: 40px;
    border-bottom: 1px solid ${props => props.theme.background2};
    & > ${SizeCell}, & > ${ModifiedCell} {
        justify-content: right;
    }
    &:hover {
        background-color: ${props => props.theme.background1};
    }
`;

const ErrorBanner = styled.div`
    height: 50px;
    display: flex;
    font-weight: 500;
    white-space: nowrap;
    align-items: center;
    overflow: hidden;
    overflow-x: auto;
    color: ${props => props.theme.error};
    background-color: ${props => props.theme.errorBackground};
    & > span {
        flex-shrink: 0;
    }
    &:before,
    &:after {
        content: "";
        height: 100%;
        width: 15px;
        display: block;
        flex-shrink: 0;
    }
`;

const sizeToString = (size: number) => {
    if (size < 1000) {
        return `${size.toFixed(0)} B`;
    }
    if (size < 1000000) {
        return `${(size / 1000).toFixed(2)} kB`;
    }
    if (size < 1000000000) {
        return `${(size / 1000000).toFixed(2)} MB`;
    }
    if (size < 1000000000000) {
        return `${(size / 1000000000).toFixed(2)} GB`;
    }
    return `${(size / 1000000000000).toFixed(2)} TB`;
};

const pad = (value: number) => value.toFixed().padStart(2, "0");

const dateToString = (date: Date) =>
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
        date.getDate()
    )} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(
        date.getSeconds()
    )}`;

const generateCompare = (sortMethod: SortMethod) => {
    switch (sortMethod.column) {
        case 0:
            return (
                a: DirectoryChild | FileChild,
                b: DirectoryChild | FileChild
            ) => {
                if (a instanceof DirectoryChild) {
                    if (b instanceof DirectoryChild) {
                        return (
                            sortMethod.direction * a.name.localeCompare(b.name)
                        );
                    } else {
                        return -1;
                    }
                } else {
                    if (b instanceof DirectoryChild) {
                        return 1;
                    } else {
                        return (
                            sortMethod.direction * a.name.localeCompare(b.name)
                        );
                    }
                }
            };
        case 1:
            return (
                a: DirectoryChild | FileChild,
                b: DirectoryChild | FileChild
            ) => {
                if (a instanceof DirectoryChild) {
                    if (b instanceof DirectoryChild) {
                        return (
                            sortMethod.direction * a.name.localeCompare(b.name)
                        );
                    } else {
                        return -1;
                    }
                } else {
                    if (b instanceof DirectoryChild) {
                        return 1;
                    } else {
                        return (
                            sortMethod.direction * Math.sign(a.size - b.size)
                        );
                    }
                }
            };
        case 2:
            return (
                a: DirectoryChild | FileChild,
                b: DirectoryChild | FileChild
            ) => {
                if (a instanceof DirectoryChild) {
                    if (b instanceof DirectoryChild) {
                        return (
                            sortMethod.direction * a.name.localeCompare(b.name)
                        );
                    } else {
                        return -1;
                    }
                } else {
                    if (b instanceof DirectoryChild) {
                        return 1;
                    } else {
                        return (
                            sortMethod.direction *
                            Math.sign(
                                a.modified.getTime() - b.modified.getTime()
                            )
                        );
                    }
                }
            };
        default:
            throw new Error(
                `unexpected sort column index ${sortMethod.direction}`
            );
    }
};

export default function Content(props: ContentProps) {
    const [state, setState] = React.useState({
        status: Status.Loading,
        children: [],
        error: null,
    } as State);
    React.useEffect(() => {
        const request = new XMLHttpRequest();
        setState({
            status: Status.Loading,
            children: [],
            error: null,
        });
        request.onload = () => {
            const children = [
                ...Array.prototype.map.call(
                    request.response.querySelectorAll("CommonPrefixes"),
                    node => new DirectoryChild(node.textContent)
                ),
                ...Array.prototype.map.call(
                    request.response.querySelectorAll("Contents"),
                    node =>
                        new FileChild(
                            node.querySelector("Key").innerHTML,
                            parseInt(node.querySelector("Size").innerHTML),
                            new Date(
                                node.querySelector("LastModified").innerHTML
                            )
                        )
                ),
            ] as (DirectoryChild | FileChild)[];
            if (children.length > 0) {
                setState({
                    status: Status.Success,
                    children,
                    error: null,
                });
            } else {
                setState({
                    status: Status.Error,
                    children,
                    error: `Path "${
                        request.response.querySelector("Prefix").innerHTML
                    }" not found`,
                });
            }
        };
        const url = `${S3_URL}?${new URLSearchParams({
            "list-type": "2",
            delimiter: "/",
            "encoding-type": "url",
            "max-keys": "1000000",
            prefix:
                props.pathComponents.length > 0
                    ? `${props.pathComponents.join("/")}/`
                    : "",
        })}`;
        request.onerror = () => {
            setState({
                status: Status.Error,
                children: [],
                error: `HTTP GET "${url}" failed`,
            });
        };
        request.open("GET", url);
        request.responseType = "document";
        request.send();
        return () => {
            request.abort();
        };
    }, [props.pathComponents]);
    const [sortMethod, setSortMethod] = React.useState({
        direction: 1,
        column: 0,
    } as SortMethod);
    const prefix =
        props.pathComponents.length > 0
            ? `${props.pathComponents.join("/")}/`
            : "";
    const [headerRef, headerDimensions] = useDimensions<HTMLDivElement>();
    const [childrenRef, childrenDimensions] = useDimensions<HTMLDivElement>();
    return (
        <StyledContent header={state.status === Status.Success ? 50 : 0}>
            <Header
                ref={headerRef}
                visible={state.status === Status.Success}
                delta={
                    headerDimensions.width != null &&
                    childrenDimensions.width != null &&
                    headerDimensions.width > 0 &&
                    childrenDimensions.width > 0
                        ? headerDimensions.width - childrenDimensions.width
                        : 0
                }
            >
                <React.Fragment>
                    <HeaderNameCell
                        sortMethod={sortMethod}
                        onClick={() => {
                            setSortMethod(sortMethod => ({
                                direction: (sortMethod.column === 0
                                    ? -sortMethod.direction
                                    : sortMethod.direction) as 1 | -1,
                                column: 0,
                            }));
                        }}
                    >
                        <span>Name</span>
                        <Caret />
                    </HeaderNameCell>
                    <HeaderSizeCell
                        sortMethod={sortMethod}
                        onClick={() => {
                            setSortMethod(sortMethod => ({
                                direction: (sortMethod.column === 1
                                    ? -sortMethod.direction
                                    : sortMethod.direction) as 1 | -1,
                                column: 1,
                            }));
                        }}
                    >
                        <span>Size</span>
                        <Caret />
                    </HeaderSizeCell>
                    <HeaderModifiedCell
                        sortMethod={sortMethod}
                        onClick={() => {
                            setSortMethod(sortMethod => ({
                                direction: (sortMethod.column === 2
                                    ? -sortMethod.direction
                                    : sortMethod.direction) as 1 | -1,
                                column: 2,
                            }));
                        }}
                    >
                        <span>Modified</span>
                        <Caret />
                    </HeaderModifiedCell>
                </React.Fragment>
            </Header>
            <Body>
                {state.status === Status.Loading && (
                    <Loading>
                        <Spinner branches={12} period={1.2} />
                    </Loading>
                )}
                <Children
                    ref={childrenRef}
                    visible={state.status === Status.Success}
                >
                    {state.children
                        .sort(generateCompare(sortMethod))
                        .map(child =>
                            child instanceof DirectoryChild ? (
                                <Child key={child.name}>
                                    <NameCell>
                                        <Directory />
                                        <a href={`#/${child.name}`}>
                                            {child.name.slice(prefix.length)}
                                        </a>
                                    </NameCell>
                                    <SizeCell>–</SizeCell>
                                    <ModifiedCell>–</ModifiedCell>
                                </Child>
                            ) : (
                                <Child key={child.name}>
                                    <NameCell>
                                        <File />
                                        <a
                                            href={`${S3_WEBSITE_URL}/${child.name}`}
                                        >
                                            {child.name.slice(prefix.length)}
                                        </a>
                                    </NameCell>
                                    <SizeCell>
                                        {sizeToString(child.size)}
                                    </SizeCell>
                                    <ModifiedCell>
                                        {dateToString(child.modified)}
                                    </ModifiedCell>
                                </Child>
                            )
                        )}
                </Children>
                {state.status === Status.Error && (
                    <ErrorBanner>
                        <span>{state.error}</span>
                    </ErrorBanner>
                )}
            </Body>
        </StyledContent>
    );
}
