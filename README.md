

character -> individual_event -> event_plaza -> people_event -> simulation_engine

event_plaza: dict[str, list[character]]
event_plaza = {
    "acquaintance": [obj1, obj2, obj3],

}

```
SimuWorld
├─ app
│  ├─ api
│  │  └─ v1
│  ├─ core
│  │  ├─ generation
│  │  │  ├─ human.py
│  │  │  ├─ name.py
│  │  │  └─ __init__.py
│  │  ├─ person
│  │  │  ├─ character.py
│  │  │  ├─ events.py
│  │  │  └─ __init.py
│  │  ├─ probability
│  │  │  ├─ func.py
│  │  │  └─ __init__.py
│  │  └─ simulation
│  │     ├─ engine.py
│  │     ├─ events.py
│  │     ├─ later.py
│  │     └─ __init__.py
│  ├─ models
│  │  ├─ crud.py
│  │  ├─ table.py
│  │  └─ __init__.py
│  ├─ schemas
│  ├─ services
│  ├─ utils
│  └─ __init__.py
├─ README.md
├─ run.py
└─ web