Vue.component('account-node',{
    delimiters: ["[[","]]"],
    template: `
        <div class="node" v-if="areZeroSaldoAccountsVisible || accountSaldo != 0">
            <div class="node-header">
                <span class="node-opener" v-if="hasChild" v-on:click="opened = !opened">
                    <span v-show="opened" style="float: left;width: 10px;">-</span>
                    <span v-show="!opened" style="float: left;width: 10px;">+</span>
                </span>
                <span class="node-opener" v-else>
                    <span style="float: left;width: 10px;">&nbsp;</span>
                </span>
                <a v-bind:href="'/operating_account/'+accountId+'/detail'">[[accountTitle]]</a>
                <span class="saldo" v-if="accountSaldo != null">[[accountSaldo.toLocaleString()]]</span>
                <span class="btn-group" role="group" v-if="!hasChild">
                    <button v-bind:class="debet_class" v-on:click="set_action('debet'); $emit('debet-select',action?description:-1)">Д</button>
                    <button v-bind:class="credit_class" v-on:click="set_action('credit'); $emit('credit-select',action?description:-1)">К</button>
                </span>
            </div>
            <div class="nodes-list" v-if="children != null" v-show="opened">
                <account-node v-for="child in children"
                    v-bind:account-id="child.account_pk"
                    v-bind:account-title="child.name"
                    v-bind:account-fullname="child.fullname"
                    v-bind:account-saldo="child.saldo"
                    v-bind:has-child="child.has_child"
                    v-on:debet-select="$emit('debet-select',$event)"
                    v-on:credit-select="$emit('credit-select',$event)"
                    v-bind:selected-debet="selectedDebet"
                    v-bind:selected-credit="selectedCredit"
                    v-bind:last-operation="last_operation"
                    v-bind:areZeroSaldoAccountsVisible="areZeroSaldoAccountsVisible">
                </account-node>
            </div>
            <div v-bind:id="accountId+'-message-log'"></div>
            <div v-show="last_operation==null">[[last_operation]]</div>
        </div>
    `,
    props: {
        accountId: {
            type:Number,
            default: -1
        },
        accountTitle: {
            type: String,
            default: "Счет"
        },
        accountFullname: {
            type: String, default: "Счет"
        },
        isOpened: {
            type: Boolean,
            default: false
        },
        accountSaldo: {
            type: Number,
            default: null
        },
        hasChild: {
            type: Boolean,
            default: true
        },
        selectedDebet: {
            type: Number, default: -1
        },
        selectedCredit: {
            type: Number, default: -1
        },
        lastOperation: {
            type: Object, default: null
        },
        areZeroSaldoAccountsVisible: {
            type: Boolean,
            default: true
        }
    },
    computed: {
        opened: {
            get() {
                return this.isOpened
            },
            set(value) {
                this.isOpened = value;
                if (this.children == null) {
                    this.load_chidlren(this.accountId);
                    this.show_message("Загрузка...");
                }
            }
        },
        description() {
            return {
                id: this.accountId,
                name: this.accountFullname,
            }
        },
        debet_class() {
            return this.action == 'debet' && this.selectedDebet == this.accountId ? 'btn btn-primary' : 'btn btn-outline-primary';
        },
        credit_class() {
            return this.action == 'credit' && this.selectedCredit == this.accountId ? 'btn btn-primary': 'btn btn-outline-primary';
        },
        last_operation() {
            if (this.lastOperation) {
                let dsaldo = 0;
                if (this.lastOperation.debet.pk==this.accountId)
                    dsaldo = this.lastOperation.amount;
                else if (this.lastOperation.credit.pk==this.accountId)
                    dsaldo = - this.lastOperation.amount;
                else
                    return this.lastOperation;
                if(this.accountSaldo)
                    this.accountSaldo += dsaldo;
            }
            return null;
        }
    },
    methods: {
        load_chidlren(pk) {
            let url = "/operating_account/tree_json/8000".replace("8000", pk);
            $.ajax({
                method: "GET", url: url,
                success: this.set_children,
                error: this.show_error
            })
        },
        set_children(data) {
            this.children = data.children;
            this.show_message("");
            /*or (let child of data.children) {
                list.append(getNode(child.name, child.fullname, child.saldo, child.account_pk, child.has_child));
            }
            console.log(data);*/
        },
        show_message(message) {
            $('#'+this.accountId+'-message-log').html(message);
        },
        set_action(value) {
            if (this.action == value) {
                this.action = null;
                if (value == 'debet')
                    this.selectedDebet = -1;
                else if (value == 'credit')
                    this.selectedCredit = -1;

            }
            else {
                this.action = value;
            }
        }
    },
    data: function() {
        return {
            children: null,
            action: null,
        }
    }
})

