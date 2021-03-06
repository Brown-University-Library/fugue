#! python
#TODO: Comments, particularly in the `tools` module.

#TODO: Do I actually need all this?
import logging
import os
from sys import argv, executable
from pathlib import Path
import re

import yaml
from lxml import etree as ET

#Used for static file moving/deleting.
from distutils.dir_util import copy_tree
import shutil

# Used for pre-/post-processing.
import subprocess

# Makes this a nice CLI.
import click

from fugue.tools.datasource_handlers import DSHandler_Factory
from fugue.tools import *

HUGE_PARSER = ET.XMLParser(huge_tree=True)
PYTHON_EXEC = executable

def process(commands):
    """Runs `commands`, an array of arrays. Used by preprocess() and postprocess()."""
    #TODO: Should be an option to supress exceptions here.
    if commands:
        for command in commands:
            # Make sure we run outside scripts with the same python as fugue.
            cmd = [ PYTHON_EXEC if x == 'python' else x for x in command ]
            logging.info("Running %s" % (' '.join(cmd), ))
            ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if ret.returncode == 0:
                logging.debug("Ran '%s'. Result: %s" % (' '.join(ret.args), ret.stdout.decode()))
            else:
                raise RuntimeError("process() command '%s' failed. Error: %s" % (' '.join(ret.args), ret.stderr.decode()))

def _load_config(ctx, file):
    logging.debug("Loading configuration file %s." % file)
    if ctx.obj == None: ctx.obj = {}
    with Path(file).open('r') as f:
        ctx.obj['settings'] = yaml.load(f, Loader=yaml.FullLoader)
    
    ctx.obj['project-output'] = Path(ctx.obj['settings']['site']['root']).resolve()
    logging.debug("Loaded configuration file.")

def _output_dir(ctx):
    outp = Path(ctx.obj['project_root']) / ctx.obj['settings']['site']['root']
    outp = outp.resolve()
    logging.debug("Checking for and returning directory at %s" % outp)
    if not outp.exists():
        outp.mkdir(parents=True)
    return outp


HERE = Path().resolve()

@click.group(invoke_without_command=True, chain=True)
@click.option('--log-level', '-L', 
                type=click.Choice(['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']),
                default="WARNING", help="Set logging level. Defaults to WARNING.")
@click.option('--project', '-p', default=Path('.', 'fugue.project.yaml'), 
                type=click.Path(), help=r"Choose the project configuration file. Defaults to ./fugue.project.yaml. Ignored if `fugue build` is called with a repository URL.")
@click.option('--data', '-d',  default=Path('.', 'fugue-data.xml'), 
                type=click.Path(), help=r"Choose the data file fugue will create and use. Defaults to ./fugue-data.xml. Ignored if `fugue build` is called with a repository URL.")
@click.pass_context
def fugue(ctx, log_level, project, data):
    """Static site generator using XSL templates."""

    """By default, looks at fugue.project.yaml in the current directory and completes all tasks
       needed to generate a complete site.
    """
    #TODO: option to not supress stdout and stderr in subprocess.run() calls.
    #TODO: Make logging more configurable.
    logging.basicConfig(level=getattr(logging, log_level))

    click.echo("Starting fugue")

    #Load configuration file.
    ctx.obj = {'data_file': Path(data), 
               'config_file': Path(project),}

    try:
        _load_config(ctx, project)
        
        ctx.obj['project_root'] = Path(project).parent.resolve()
        os.chdir(ctx.obj['project_root'])
        logging.debug('Changed directory to %s' % ctx.obj['project_root'])
    except FileNotFoundError as e:
        logging.debug(r"Loading config file failed. Hopefully we're giving build() a repository on the command line.")
        #Since chain=True, we can't tell which subcommand is being invoked :(.
        if ctx.invoked_subcommand == None:
            #Fail.
            raise RuntimeError("No Fugue configuration file found and we are not building from a git repository.")
    
    if ctx.invoked_subcommand is None:
        logging.debug("No subcommand invoked. Calling build().")
        ctx.invoke(build)

@fugue.command()
@click.pass_context
def update(ctx):
    """`git pull` the project's repository."""
    targ = str(ctx.obj['project_root'])
    cmd = "git -C %s pull origin" % (targ, )
    logging.info("Running '%s'." % cmd)
    ret = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.debug("Finished 'git pull': %s" % ret.stdout.decode())
    if ret.returncode != 0:
        raise RuntimeError("Failed to pull repository. Error: %s" % ret.stderr.decode())
    _load_config(ctx, ctx.obj['config_file'])

@fugue.command()
@click.argument("repository", required=False)
@click.option('--no-update', '-n', is_flag=True, 
                help=r"Do not `git pull` this repository.")
@click.option('--no-fetch', '-N', is_flag=True,
                help=r"Do not pull or clone any git repositories. Implies -n.")
@click.option('--no-outside-tasks', '-o', is_flag=True,
                help=r"Do not execute pre- or post-processing tasks.")
@click.pass_context
def build(ctx, repository, no_update, no_fetch, no_outside_tasks):
    """Build the entire site from scratch.
    
    Completes all other steps; this is done by 
    default if no other command is specified.
    
    If <repository> is provided, it is assumed to be the URL of a git repository; it
    will be cloned into a subdirectory of the current directory, then the fugue project
    there will be built. The `project` and `data` arguments provided to `fugue` will be
    interpreted relative to the repository's root."""
    logging.debug("Beginning build()")
    click.echo(r"Running 'fugue build'. (Re)-building entire site.")

    if repository != None:
        logging.debug("cloning %s." % repository)
        localrepo = Path(repository).stem

        logging.debug('local repository directory is %s' % localrepo)
        logging.debug('localrepo:' + str(Path(localrepo)))
        logging.debug('data: ' + str(ctx.obj['data_file']))
        logging.debug('project: ' + str(ctx.obj['config_file']))
        logging.debug('data_file will be %s' % str(Path(localrepo, ctx.obj['data_file'])))
        logging.debug('project config_file will be %s' % str(Path(localrepo, ctx.obj['config_file'])))

        cmd = "git clone %s %s" % (repository, localrepo)
        logging.info("Running '%s'." % cmd)
        ret = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("Finished 'git clone': %s" % ret.stdout.decode())
        if ret.returncode != 0:
            raise RuntimeError("Failed to clone repository. Error: %s" % ret.stderr.decode())
        
        logging.debug('Changing working directory to %s' % localrepo)
        os.chdir(Path(localrepo))
        ctx.obj['config_file'] = ctx.obj['config_file'].resolve()
        #TODO: Fail more elegantly if we can't find a config file.
        _load_config(ctx, ctx.obj['config_file'])
        logging.debug("project config_file '%s' loaded." % str(ctx.obj['config_file']))
        ctx.obj['project_root'] = Path().resolve()
        
        logging.debug("Working directory changed to %s" % str(Path().resolve()))
        
        # Do some error checking before we spend an hour downloading gigabytes of data.
        if not ctx.obj['data_file'].parent.exists():
            #TODO: Should I just make it instead?
            logging.error("Data file %s's parent directory does not exist" % str(ctx.obj['data_file']))
            raise FileNotFoundError("Data file %s's parent directory does not exist.")
        
        #Verify we can touch this file before we go further.
        ctx.obj['data_file'].touch(exist_ok=True)
        logging.debug("Data file: %s" % str(ctx.obj['data_file'].resolve()))
        
        if not Path(ctx.obj['config_file']).exists():
            raise FileNotFoundError("No fugue project found at %s." % str(Path(ctx.obj['config_file'])))
    elif not ctx.obj.get('settings', False):
        raise FileNotFoundError("No fugue project found.")

    logging.debug("Settings: " + str(ctx.obj['settings']))
    logging.debug("Building. Project root: %s" % str(ctx.obj['project_root']))

    if not (no_update or no_fetch or repository):
        ctx.invoke(update)

    #ctx.invoke(clear)

    if not no_fetch:
        ctx.invoke(fetch)
    
    if not no_outside_tasks:
        ctx.invoke(preprocess)
    ctx.invoke(collect)
    ctx.invoke(static)
    ctx.invoke(generate)

    if not no_outside_tasks:
        ctx.invoke(postprocess)
    
    click.echo("Building complete.")
    logging.debug("Ending build()")

#TODO: Finish and test.
'''
@fugue.command()
@click.pass_context
def clear(ctx):
    """Deletes all contents of the output directory.

    Preserves files matching the patterns in settings.clear.exclude"""

    #NOTE: os.walk() is our friend. Maybe also fnmatch.fnmatch().


    outdir = _output_dir(ctx)
    click.echo("Clearing the output directory.")
    excludes = ctx.obj['settings'].get('clear', {}).get('exclude', [])
    logging.debug("Excludes: " + str(excludes))
    def exclude_path(pth):
        """Do any of the patterns match pth?"""
        for pat in excludes:
            if pth.match(pat):
                return True
        return False

    for dr in [x for x in outdir.iterdir() if x.is_dir() and not exclude_path(x.resolve())]:
        shutil.rmtree(str(dr.resolve()))
    
    for fl in [x for x in outdir.iterdir() if x.is_file()]:
        os.unlink(str(fl.resolve()))
'''
        
@fugue.command()
@click.pass_context
def preprocess(ctx):
    """Runs all preprocessing directives."""
    #TODO: Should be an option to supress exceptions here.
    outdir = _output_dir(ctx)
    logging.debug("Preprocess: Output dir: %s" % outdir)
    click.echo("Running preprocess tasks.")
    commands = ctx.obj['settings'].get('preprocess', [])
    process(commands)

@fugue.command()
@click.pass_context
def fetch(ctx):
    """Fetches git repositories."""
    #For now we'll use subprocess.run(). Is there any benefit to dulwich instead?
    #TODO: should probably put this logic in separate modules so we can support svn, fossil, SFTP, etc. sources.
    #TODO: git might should support checking out specific branches/tags.

    click.echo('Fetching repositories.')

    repositories = ctx.obj['settings'].get('repositories', [])
    logging.info('Pulling %d repositories.' % len(repositories))

    for repo in repositories:
        if not Path(repo['target']).exists():
            targ = str(Path(repo['target']).resolve())
            rootdir = str(Path(repo['target']).resolve().parent)
            cmd = "git -C %s clone %s %s" % (rootdir, repo['remote'], targ)
            logging.info('%s does not exist; cloning %s into it.' % (repo['target'], repo['remote']))
            logging.debug("Running '%s'." % cmd)
            ret = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.debug("Finished 'git clone': %s" % ret.stdout.decode())
            if ret.returncode != 0:
                raise RuntimeError("Failed to clone repository. Error: %s" % ret.stderr.decode())
        else: 
            targ = str(Path(repo['target']).resolve())
            cmd = "git -C %s pull" % (targ, )
            logging.info("Running '%s'." % cmd)
            ret = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.debug("Finished 'git pull': %s" % ret.stdout.decode())
            if ret.returncode != 0:
                raise RuntimeError("Failed to pull repository. Error: %s" % ret.stderr.decode())

@fugue.command()
@click.pass_context
def collect(ctx):
    """Collects all datasources.
    
    Collects all data described in fugue.project.yaml under data-sources
    into the xml file specified by --data. Does not imply `fetch`."""
    click.echo("Collecting data")
    outdir = _output_dir(ctx)
    logging.debug("Collecting. Output dir: %s" % outdir)
    xmlroot = ET.Element('fugue-data')
    
    projroot = ET.SubElement(xmlroot, 'fugue-config')

    #Convert our settings file to XML and add to the XML data document.
    dict2xml(ctx.obj['settings'], projroot)

    dssroot = ET.SubElement(xmlroot, 'data-sources')
    dss = ctx.obj['settings']['data-sources']
    for dsname, ds in dss.items():
        logging.info("Collecting datasource '%s'." % dsname)
        #TODO: Dynamically load modules to deal with different DS types.
        dsroot = ET.SubElement(dssroot, dsname)
        
        handler = DSHandler_Factory().build(ds)
        handler.write(dsroot)


    data_file = ctx.obj['data_file']

    logging.info('Writing XML data to %s.' % str(data_file))
    data_file.touch(exist_ok=True)
    
    xmlroot.getroottree().write(str(data_file), pretty_print=True, encoding="utf8")
    #with data_file.open(mode="wb") as outpfile:
    #    outpfile.write(ET.tostring(xmlroot, pretty_print=True))
    
    #No need to read this if it's already in memory.
    ctx.obj['xmldata'] = xmlroot
    
@fugue.command()
@click.pass_context
def static(ctx):
    """Copies static directories into output."""
    click.echo("Handling static files.")
    outdir = _output_dir(ctx)
    logging.debug("Moving static files. Output dir: %s" % outdir)
    sss = ctx.obj['settings']['static-sources']
    logging.info('Deleting static directories')
    for ssname, ss in sss.items():
        if ss['target'] != '':
            target = Path(outdir, ss['target']).resolve()
            logging.debug("Deleting %s." % target)
            if target.exists():
                #TODO: Why does this sometimes throw errors if I don't ignore_errors?
                shutil.rmtree(target, ignore_errors=False)

    logging.info('Copying static files.')
    for ssname, ss in sss.items():
        source = Path(ss['source']).resolve()
        target = Path(ctx.obj['project-output'], ss['target']).resolve()
        logging.debug("Moving " + str(source) + ' to ' + str(target) + ".")
        copy_tree(str(source), str(target))

@fugue.command()
@click.pass_context
def generate(ctx):
    """Generates pages from XSL templates. Does not imply `collect` and will fail if the file specified by --data doesn't exist."""
    #TODO: Two-step generation (HTML -> XSL -> HTML)
    click.echo('Generating pages.')
    outdir = _output_dir(ctx)
    logging.debug("Generating. Output directory: %s" % str(outdir))

    pages = ctx.obj['settings']['pages']

    data_file = ctx.obj['data_file']
    
    if 'xmldata' in ctx.obj:
        logging.debug("Using previously-loaded data.")
    else:
        logging.debug("Reading data from %s" % str(data_file))
        with  data_file.open("rb") as fl:
            fdata = fl.read()
        ctx.obj['xmldata'] = ET.fromstring(fdata, HUGE_PARSER)
    data = ctx.obj['xmldata']
    
    for pagename, page in pages.items():
        logging.info("Generating page '%s'." % pagename)
        xslt = ET.parse(page['template'])
        transform = ET.XSLT(xslt)

        #TODO: Pagination should be optional.
        params = {
            'pagename':     "'{}'".format(pagename),
            'output_dir':   "'{}'".format(outdir.as_posix())
        }

        for k, v in page.items():
            if k not in params.keys():
                if type(v) in (int, float):
                    params[k] = str(v)
                if type(v) == str:
                    if v.startswith('xpath:'):
                        params[k] = v[len('xpath:'):]
                    elif 'items' == k: #TODO: Remove. Legacy, for pagination.
                        params[k] = v
                    else: #TODO: This will break stuff if v contains a '
                        params[k] = "'{}'".format(v)
        
        result = transform(data, **params)
        
        #TODO: Make this an option somewhere. 

        if page['uri']: #If uri is false, just discard the from this template.
            flname = page['uri']
            target = Path(outdir, flname)
            
            if not target.parent.exists():
                target.parent.mkdir(parents=True)
            
            logging.debug("Outputting "+str(target))
            #with target.open('wb') as f:
            result.write_output(str(target))

@fugue.command()
@click.pass_context
def postprocess(ctx):
    """Runs all postprocessing directives."""
    outdir = _output_dir(ctx)
    logging.debug("Postprocessing. Output dir: %s" % outdir)
    click.echo("Running postprocess tasks.")
    commands = ctx.obj['settings'].get('postprocess', [])
    process(commands)

if __name__ == '__main__':
    STARTED_IN = Path().resolve()
    fugue()
    os.chdir(STARTED_IN)