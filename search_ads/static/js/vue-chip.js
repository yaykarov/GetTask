Vue.component('chip',{
    delimiters: ["${","}"],
    template: `
        <span v-bind:style="body_style" v-if="active" v-bind:active="active">
            \${ value }
            <i class="fa fa-times" v-bind:style="close_btn_style" v-on:click="$emit('chip-close', value)"></i>
        </span>
    `,
    props: {
        value: String
    },
    data: function() {
        return {
            close_btn_style: {
                cursor: "pointer",
                "margin": "5px",
            },
            body_style: {
                "border-radius": "1em",
                "padding-left": "5px",
                "padding-right": "5px",
                "padding-top": "3px",
                "padding-bottom": "3px",
                border: "1px solid #007bff",
                "word-wrap": "normal",
                color: "#007bff"
            },
            active: true
        }
    }
});
Vue.component('select-auto',{
    delimiters: ["[[","]]"],
    template: `
        <span>
            <div>
                <chip v-for="svalue in selected" v-bind:value="svalue" v-on:chip-close="removeSelected"></chip>
            </div>
            <!--<input v-on:keypress.enter.prevent="addSelected" v-bind:list="name+'-datalist'" autocomplete="off" v-model:value="value" v-bind:style="input_style">-->
            <select v-on:change="addSelected(event.srcElement.value)" v-model:value="value" placeholder="выберите значение">
                <option v-for="cvalue in dsource" v-bind:value="cvalue">[[cvalue]]</option>
            </select>
            <div><input type="hidden" v-for="item in selected" v-bind:name="name" v-bind:value="item"></div>
        </span>
    `,
    props: {
        dataselected: {
            type: String,
            default: function() {return "" }
        },
        datasource: {
            type: String,
            default: function() {return "" }
        },
        breaker: {
            type: String,
            default: function() { return ", " }
        },
        name: String
    },
    data: function() {
        return {
            value: '',
            input_style: {
                border: "1px solid #007bff",
                "border-radius": "2em"
            }
        }
    },
    methods: {
        addSelected(e) {
            //e.preventDefault();
            if (!this.selected.includes(this.value) && (this.dsource.includes(this.value) || this.datasource==""))
                this.dataselected += this.breaker + this.value;
            this.value = '';
        },
        removeSelected(value) {
            let index = this.selected.indexOf(value);
            if (index != -1) {
                let re = new RegExp("("+this.breaker+")?"+value+"("+this.breaker+")?");
                this.dataselected = this.dataselected.replace(re,this.breaker);
            }
        }
    },
    computed: {
        dsource: function() {
            return this.datasource.split(this.breaker).filter(item => item != "");
        },
        selected: function() {
            return this.dataselected.split(this.breaker).filter(item => item != "");
        }
    }
});
Vue.component('chip-simple',{
    delimiters: ["[[","]]"],
    template: `
        <span>
            <div>
                <chip v-for="svalue in selected" v-bind:value="svalue" v-on:chip-close="removeSelected"></chip>
            </div>
            <input v-on:keypress.enter.prevent="addSelected" v-bind:list="name+'-datalist'" autocomplete="off" v-model:value="value" v-bind:style="input_style">
            <div><input type="hidden" v-for="item in selected" v-bind:name="name" v-bind:value="item"></div>
        </span>
    `,
    props: {
        dataselected: {
            type: String,
            default: function() {return "" }
        },
        datasource: {
            type: String,
            default: function() {return "" }
        },
        breaker: {
            type: String,
            default: function() { return ", " }
        },
        name: String
    },
    data: function() {
        return {
            value: '',
            input_style: {
                border: "1px solid #007bff",
                "border-radius": "2em"
            }
        }
    },
    methods: {
        addSelected(e) {
            e.preventDefault();
            if (!this.selected.includes(this.value) && (this.dsource.includes(this.value) || this.datasource==""))
                this.dataselected += this.breaker + this.value;
            this.value = '';
        },
        removeSelected(value) {
            let index = this.selected.indexOf(value);
            if (index != -1) {
                let re = new RegExp("("+this.breaker+")?"+value+"("+this.breaker+")?");
                this.dataselected = this.dataselected.replace(re,this.breaker);
            }
        }
    },
    computed: {
        dsource: function() {
            return this.datasource.split(this.breaker).filter(item => item != "");
        },
        selected: function() {
            return this.dataselected.split(this.breaker).filter(item => item != "");
        }
    }
});
Vue.component('modal-fade',{
    delimiters: ["${","}"],
    template: `
        <div class="modal fade" v-bind:id="modalId" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" v-bind:aria-hidden="modalActive">
          <div class="modal-dialog" role="document">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="exampleModalLabel">\${modalTitle}</h5>
                <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                  <span aria-hidden="true">&times;</span>
                </button>
              </div>
              <div class="modal-body">
                <slot></slot>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                <button type="button" class="btn btn-primary" data-dismiss="modal" v-on:click="$emit('modal-ok')">Save changes</button>
              </div>
            </div>
          </div>
        </div>
    `,
    props: {
        modalTitle: {
            type: String,
            default: "Заголовок"
        },
        modalActive: {
            type: Boolean,
            default: false
        },
        modalId: String
    },
    methods: {
        toggleModal(){
            if (value)
                $("#"+this.modalId).modal('toggle');
        }
    }
});