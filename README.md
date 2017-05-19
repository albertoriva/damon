# Damon
An object-oriented framework to develop computational pipelines in HPC environments.

*Note: the following is only an overview of the DAMON system. A detailed manual,
including API documentation, is coming soon.*

**DAMON** (Distributed Analysis MONitor) is an open-source,
object-oriented Python framework for the development of computational
pipelines, specifically designed for NGS data analysis in a cluster
computing environment. Pipelines are built out of reusable objects
implementing analysis steps (e.g. short-read alignment, transcript
quantification) and are controlled by simple configuration files
detailing the experimental setup, the input data, and the steps to be
performed.

## General architecture

Pipeline execution is controlled by a [Director](https://github.com/albertoriva/damon/blob/master/Director.py) 
object that, given an [Actor](https://github.com/albertoriva/damon/blob/master/Actor.py) object representing the 
pipeline, performs the necessary setup and executes all required steps. Each step is represented by a 
[Line](https://github.com/albertoriva/damon/blob/master/Lines.py) object. Each Line provides a set of standard methods: 
Setup, Verification, Pre-Execution, Execution, Post-Execution, and Reporting. Thanks to this standard API, steps 
can be freely combined: for example, changing the short-read aligner from Bowtie to STAR only requires swapping 
one Line object for another in the pipeline definition.

## Input data

Through the [SampleCollection](https://github.com/albertoriva/damon/blob/master/Lines.py) object, DAMON is able 
to handle any number of experimental conditions, biological replicates, and technical replicates, easily supporting
complex experimental designs with no changes to the pipeline structure.

## Cluster operation

DAMON automatically handles submission and management of jobs to the cluster, ensuring proper job sequencing and coordination. 
It relies on a generic *submit* command that handles both **slurm** and **PBS** clusters. **TODO**: provide a reference
implementation of the *submit* command.

## Reporting 

DAMON pipelines automatically generate an HTML report of their execution. Each step may add one or more sections to the report
containing text, tables, figures, links to downloadable files. The report follows a a standard template that can be customized 
by specializing the Actor object.

## Dependencies

DAMON is a stand-alone package written in Python 2.7. The companion [Pipelines](https://github.com/albertoriva/pipelines) package
provides examples of pipelines build with DAMON for various bioinformatics applications, including RNA-seq, ChIP-seq, ATAC-seq, 
methylation analysis, variant discovery, genome annotation). The examples in Pipelines, in turn, rely heavily on scripts in the 
[Bioscripts](https://github.com/albertoriva/bioscripts) package.
