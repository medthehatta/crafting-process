# Enhancement Roadmap

## 0. Resolve a nitpick about annotating processes for lookup

The DSL currently provides all the attribute parameters like duration=N etc. as arguments to the Process initializer.  This is sometimes required for predefined arguments that can be relevant to any process like duration, but sometimes I would like to provide simple freeform annotations in the DSL that can be used for library lookup.  The Process should be willing to store these annotations even if they are not valid initializer arguments so the library can search for the processes later.

## 1. Re-implement augment.py

The current implementation of augment.py sucks.  It introduces a gross wrapper class around Process with some hardcoded methods that are quite ad-hoc.  Using the AugmentedProcess manually is not really ergonomic (I previously just had some standard ones that were universally applied to every process so we didn't need to involve the ProcessLibrary), so they don't really even satisfy their primary design goals.

What we want is to be capable of modeling some standard transformations on processes that yield new processes within the DSL.  Any function Process -> Process could be acceptable as an "augmentation".  We need to be able to attach these augmentations to the ProcessLibrary for use in the DSL in a standard way.  We then need to be able to either manually apply these augmentations to processes in the DSL, or specify that we want to apply them to whole batches of processes.  This will involve some DSL extensions and likely a reimplementation of augment.py.

## 2. Find a way to mix batch and continuous processes in a graph

Currently the processes must either all be batch or continuous in a graph, and it's implicit which is in use.  If callers use transfer rates instead of transfer that basically is what determines the disposition.

I would like a way to express _a priori_ that a process is batch or continuous (perhaps the presence or absence of a duration field is sufficient), and to have the graph resolve this: continuous processes can run in parallel, but they require their inputs are available before they can start.  Therefore the graphs consist of "concurrent combinations of batches" or "batches of concurrent combinations" nested arbitrarily.

It should still be possible to calculate process depths so the order in which processes are performed can be emitted to the user.

This actually sounds pretty difficult so this might be a multi-stage project.

## 3. Sort graph results by an arbitrary "cost" function

It happens frequently that there are quite a few ways to produce something, and many different reasons why some methods may be preferred over others.  I would therefore like to add the ability to evaluate some (scalar) function on a graph and sort the output on the function value.  Examples of this could be minimizing raw ingredient cost, or minimizing total process time, or minimizing total number of processes, or maximizing profit compared with some reference price.

Ideally we would be able to do like a lazy `topk` evaluation rather than a brute-force "load all possible graphs into memory and sort them".

## 4. Recheck integrations with crafting_frontend

There is a basic web app wrapper around this that I use, and I would like to re-evaluate its integrations with this repo so that we can enhance the frontend as well.
