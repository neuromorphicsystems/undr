import * as React from "react";
import { useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import styled, { useTheme } from "styled-components";
import * as constants from "../hooks/constants";
import { DatasetMode, StateContext, navigateToMainRoute } from "../hooks/state";
import Aws from "../icons/aws.svg";
import Close from "../icons/close.svg";
import Undr from "../icons/undr.svg";
import UndrSmall from "../icons/undr-small.svg";
import Wsu from "../icons/wsu.svg";

const StyledAbout = styled(motion.div)`
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    bottom: 0;
    z-index: 11;
    overflow: hidden;
    background-color: ${props => props.theme.background1};
    border-bottom: 1px solid ${props => props.theme.content2};
`;

const Content = styled.div`
    height: calc(100vh - ${constants.barHeight}px);
`;

const Bar = styled.div`
    height: ${constants.barHeight}px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: ${(constants.barHeight - constants.buttonHeight) / 2}px;
    border-bottom: 1px solid ${props => props.theme.background3};
`;

const Button = styled.div`
    width: ${constants.buttonHeight}px;
    height: ${constants.buttonHeight}px;
    padding: ${(constants.buttonHeight - constants.buttonIconHeight) / 2}px;
    cursor: pointer;
    border-radius: ${constants.buttonHeight / 2}px;
    transition: background-color 0.2s;
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

const Sections = styled.div`
    height: calc(100vh - ${constants.barHeight * 2}px);
    overflow: auto;
`;

const Section = styled.div`
    flex-shrink: 0;
    display: flex;
    align-items: center;
    background-color: ${props => props.theme.background1};
    padding: 20px;
    padding-right: 30px;
    gap: 20px;
    @media (max-width: 512px) {
        flex-direction: column;
        padding: 20px;
    }
    &:not(:last-of-type) {
        border-bottom: 1px solid ${props => props.theme.background2};
    }
`;

const SectionLogo = styled.div`
    width: 100px;
    display: block;
    @media (max-width: 512px) {
        display: none;
    }
    & > svg {
        display: block;
        height: 100%;
    }
`;

const SectionLogoAws = styled(SectionLogo)`
    & > svg circle {
        fill: ${props => props.theme.background0};
    }
    & > svg .letters {
        fill: ${props => props.theme.content0};
    }
`;

const SectionContent = styled.div`
    width: 100%;
    user-select: auto;
`;

const SectionTitle = styled.div`
    display: flex;
    @media (max-width: 512px) {
        display: none;
    }
`;

const SectionTitleNarrow = styled.div`
    display: none;
    @media (max-width: 512px) {
        display: flex;
        gap: 20px;
        align-items: center;
        justify-content: center;
    }
`;

const SectionLogoSmall = styled.div`
    height: 90px;
    & > svg {
        display: block;
        height: 100%;
    }
`;

const SectionLogoSmallAws = styled(SectionLogoSmall)`
    & > svg circle {
        fill: ${props => props.theme.background0};
    }
    & > svg .letters {
        fill: ${props => props.theme.content0};
    }
`;

const SectionTitleContent = styled.div`
    font-weight: 500;
    font-size: 20px;
`;

const SectionDescription = styled.div`
    padding-top: 20px;
    padding-bottom: 20px;
    text-align: justify;
    hyphens: auto;
`;

const MailLink = styled.a`
    color: ${props => props.theme.link};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-decoration: none;
    font-weight: 500;
    text-decoration: underline;
    &:hover,
    &:active {
        color: ${props => props.theme.linkActive};
    }
`;

const Link = styled(MailLink)`
    display: block;
    color: ${props => props.theme.link};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-decoration: none;
    font-weight: 500;
    text-decoration: underline;
    &:hover,
    &:active {
        color: ${props => props.theme.linkActive};
    }
`;

interface ModeInterface {
    mode: DatasetMode;
}

const ModesSection = styled.div`
    display: flex;
    flex-direction: column;
    gap: 20px;
    background-color: ${props => props.theme.background1};
    padding: 20px;
    border-bottom: 1px solid ${props => props.theme.background2};
`;

const ModeDescription = styled.div`
    text-align: justify;
`;

const Mode = styled.span<ModeInterface>`
    font-weight: 500;
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

export default function About() {
    const location = useLocation();
    const [state, _] = React.useContext(StateContext);
    const theme = useTheme();
    return (
        <StyledAbout
            initial={{ y: "-100%" }}
            animate={{
                y: 0,
                borderBottom: `1px solid ${theme.content2}`,
                transitionEnd: {
                    borderBottom: "none",
                },
            }}
            exit={{
                y: location.pathname === "/preferences" ? 0 : "-100%",
                borderBottom:
                    location.pathname === "/preferences"
                        ? "none"
                        : `1px solid ${theme.content2}`,
                transitionEnd: {
                    zIndex: 10,
                    borderBottom: "none",
                },
            }}
            transition={{ duration: constants.transitionDuration }}
        >
            <Content>
                <Bar>
                    <Button
                        onClick={() => {
                            navigateToMainRoute(state, {
                                state: { pathname: location.pathname },
                            });
                        }}
                    >
                        <Close />
                    </Button>
                </Bar>
                <Sections>
                    <ModesSection>
                        <ModeDescription>
                            In <Mode mode={"remote"}>remote</Mode> mode, only
                            index files are downloaded locally. Downloading
                            index files is required to generate BibTex
                            references or calculate the datasets&rsquo; size.
                            UNDR&rsquo;s Python library can seemlessly process
                            remote datasets, but most other languages require
                            local or raw files.
                        </ModeDescription>
                        <ModeDescription>
                            In <Mode mode={"local"}>local</Mode> mode, datasets
                            are downloaded locally as compressed files.
                            Compressed files are typically 3 to 5 times smaller
                            than their uncompressed counterparts, but they must
                            be decompressed before being processed.
                        </ModeDescription>
                        <ModeDescription>
                            In <Mode mode={"raw"}>raw</Mode> mode, datasets are
                            downloaded and decompressed. This can be useful to
                            read data with a programming language that does not
                            support UNDR&rsquo;s compression formats or to read
                            data at a specific offset (unlike compressed files,
                            uncompressed files use the same number of bytes to
                            represent each item). Compressed files are deleted
                            after decompression during the installation process
                            (see Preferences to change this behaviour).
                        </ModeDescription>
                        <ModeDescription>
                            <Mode mode={"disabled"}>Disabled</Mode> datasets are
                            ignored by all operations, as if they were not
                            listed in the configuration. Disabled datasets can
                            easily be enabled at a later time, whereas removed
                            datasets require a little more work (namely, filling
                            in their name and URL).
                        </ModeDescription>
                    </ModesSection>
                    <Section>
                        <SectionLogo>
                            <Undr />
                        </SectionLogo>
                        <SectionContent>
                            <SectionTitle>
                                <SectionTitleContent>
                                    Unified Neuromorphic Datasets Repository
                                </SectionTitleContent>
                            </SectionTitle>
                            <SectionTitleNarrow>
                                <SectionLogoSmall>
                                    <UndrSmall />
                                </SectionLogoSmall>
                                <SectionTitleContent>
                                    Unified
                                    <br />
                                    Neuromorphic
                                    <br />
                                    Datasets
                                    <br />
                                    Repository
                                </SectionTitleContent>
                            </SectionTitleNarrow>
                            <SectionDescription>
                                UNDR provides public access to Neuromorphic
                                datasets converted into a common format.
                                <br />
                                We are not the datasets&apos; authors, please
                                cite the original papers if you use them.
                            </SectionDescription>
                            <Link
                                href="https://github.com/neuromorphicsystems/undr"
                                target="_blank"
                            >
                                https://github.com/neuromorphicsystems/undr
                            </Link>
                        </SectionContent>
                    </Section>
                    <Section>
                        <SectionLogo>
                            <Wsu />
                        </SectionLogo>
                        <SectionContent>
                            <SectionTitle>
                                <SectionTitleContent>
                                    International Centre for Neuromorphic
                                    Systems
                                </SectionTitleContent>
                            </SectionTitle>
                            <SectionTitleNarrow>
                                <SectionLogoSmall>
                                    <Wsu />
                                </SectionLogoSmall>
                                <SectionTitleContent>
                                    International
                                    <br />
                                    Centre for
                                    <br />
                                    Neuromorphic
                                    <br />
                                    Systems
                                </SectionTitleContent>
                            </SectionTitleNarrow>
                            <SectionDescription>
                                UNDR was developed in the International Centre
                                for Neuromorphic Systems at Western Sydney
                                University.
                            </SectionDescription>
                            <Link
                                href="https://www.westernsydney.edu.au/icns"
                                target="_blank"
                            >
                                https://www.westernsydney.edu.au/icns
                            </Link>
                        </SectionContent>
                    </Section>
                    <Section>
                        <SectionLogoAws>
                            <Aws />
                        </SectionLogoAws>
                        <SectionContent>
                            <SectionTitle>
                                <SectionTitleContent>
                                    Open Data on Amazon Web Services
                                </SectionTitleContent>
                            </SectionTitle>
                            <SectionTitleNarrow>
                                <SectionLogoSmallAws>
                                    <Aws />
                                </SectionLogoSmallAws>
                                <SectionTitleContent>
                                    Open Data on
                                    <br />
                                    Amazon
                                    <br />
                                    Web
                                    <br />
                                    Services
                                </SectionTitleContent>
                            </SectionTitleNarrow>
                            <SectionDescription>
                                Open Data on AWS hosts most datasets for free
                                and enables robust and fast data distribution
                                world-wide.
                                <br />
                                Contact us (
                                <MailLink href="mailto:alexandre.marcireau@gmail.com">
                                    alexandre.marcireau@gmail.com
                                </MailLink>
                                ) if you would like to add your dataset to AWS.
                                <br />
                                The UNDR protocol is compatible with other cloud
                                platforms and self-hosting solutions.
                            </SectionDescription>
                            <Link
                                href="https://aws.amazon.com/opendata"
                                target="_blank"
                            >
                                https://aws.amazon.com/opendata
                            </Link>
                        </SectionContent>
                    </Section>
                </Sections>
            </Content>
        </StyledAbout>
    );
}
