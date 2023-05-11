Vue.component('bootstrap-modal', {
    delimiters: ["[[","]]"],
    template: `
        <div class="modal fade" v-bind:id="modalId" tabindex="-1" role="dialog" aria-labelledby="exampleModalLabel" aria-hidden="true" v-on:keyup.enter="modalOkCallback">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" >[[modalTitle]]</h5>
                        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        <slot></slot>
                    </div>
                    <div class="modal-log"></div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">[[ modalCancelLabel ]]</button>
                        <button type="button" class="btn btn-primary" v-on:click="modalOkCallback" tabindex="1">[[ modalOkLabel ]]</button>
                    </div>
                </div>
            </div>
        </div>
    `,
    props: {
        modalId: String,
        modalTitle: String,
        modalOkCallback: Function,
        modalOkLabel: {type:String, default: "ОК"},
        modalCancelLabel: {type:String, default: "Отмена"}
    },
    data: function(){
        return {
            
        }
    }
})