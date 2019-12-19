# Transformer Plot Merge

Merges LAS files assumed to be in a plot.
See the [Plot Clip transformer](https://github.com/AgPipeline/transformer-plotclip) for more information on clipping to plots.

## Authors

* Christophe Schnaufer, University of Arizona, Tucson, AZ
* Max Burnette, National Supercomputing Applications, Urbana, Il

## Sample Docker Command Line
Below is a sample command line that shows how the plot merge image could be run.
An explanation of the command line options used follows.
Be sure to read up on the [docker run](https://docs.docker.com/engine/reference/run/) command line for more information.

The files used in this example are available through Google Drive [ua_gantry_las_plot_merge_test_data.tar.gz](https://drive.google.com/file/d/1BdNiulDiBpS4c_mMoyKgRzvxcQNOooW3/view?usp=sharing)

```docker run --rm --mount "src=/home/test,target=/mnt,type=bind" agpipeline/plotmerge:3.0 --working_space /mnt --metadata /mnt/15c1a9d1-36b3-43fb-a7a2-0d02c76296a4_metadata-593_cleaned.json --merge_filename '/mnt/MAC Field Scanner Season 7 Range 27 Column 1.las' scanner3DTop /mnt```

This example command line assumes the files to merge are located in the `/home/test` folder of the local machine.
The name of the Docker image to run is `agpipeline/plotmerge:3.0`.

We are using the same folder for the source files and the output files.
By using multiple `--mount` options, the source and output files can be separated.

**Docker commands** \
Everything between 'docker' and the name of the image are docker commands.

- `run` indicates we want to run an image
- `--rm` automatically delete the image instance after it's run
- `--mount "src=/home/test,target=/mnt,type=bind"` mounts the `/home/test` folder to the `/mnt` folder of the running image

We mount the `/home/test` folder to the running image to make files available to the software in the image.

**Image's commands** \
The command line parameters after the image name are passed to the software inside the image.
Note that the paths provided are relative to the running image (see the --mount option specified above).

- `--working_space "/mnt"` specifies the folder to use as a workspace
- `--metadata "/mnt/15c1a9d1-36b3-43fb-a7a2-0d02c76296a4_metadata-593_cleaned.json"` is the name of the source metadata
- ` --merge_filename '/mnt/MAC Field Scanner Season 7 Range 27 Column 1.las'` the name of the file to merge LAS data into
- `scanner3DTop` the name of the sensor associated with the source files
- `/mnt` the folder containing the files to be merged 
