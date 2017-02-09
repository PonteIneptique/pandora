pandora
==========

A Tagger-Lemmatizer for Latin


### Install

For now, installation needs to be done by pulling the repository and installing the required libraries yourself.

#### Environment free

*Note* : if you have CUDA installed, you should do `pip install -r requirements-gpu.txt` instead

```bash
git clone https://github.com/hipster-philology/pandora.git
cd pandora
pip install -r requirements.txt
```

#### Virtualenv

**For CUDA-Ready machines owner**:

```bash
git clone https://github.com/hipster-philology/pandora.git
cd pandora
virtualenv env
source env/bin/activate
pip install -r requirements-gpu.txt
```

**For the others**:

```bash
git clone https://github.com/hipster-philology/pandora.git
cd pandora
virtualenv env
source env/bin/activate
pip install -r requirements.txt
```

### Scripts

#### main.py

`main.py` allows you to train your own models :

```bash
source env/bin/activate
python main.py --help
python main.py config_12c.txt --dev /path/to/dev/resources --train /path/to/train/resources
python main.py config_12c.txt --dev /path/to/dev/resources --train /path/to/train/resources --nb_epochs 1
```

#### unseen.py

`unseen.py` allows you to annotate a string or folder

```bash
source env/bin/activate
python unseen.py --help
python unseen.py config_12c.txt --string --input "Cur in theatrum, Cato severe, venisti?"
python unseen.py config_12c.txt --input /path/to/dir/to/annotate --ouput /path/to/output/dir
```
